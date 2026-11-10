"""Unit and integration tests for PORT-42 FULL_HOOKS=1 full CHDK build.

Verifies:
1. Toolchain availability and skip behavior if toolchain is missing.
2. FULL_HOOKS=1 full build execution producing out/port41-full/DISKBOOT.BIN,
   CHDK/ distribution folder, and port42_full_hooks_manifest.json.
3. FULL_HOOKS=1 manifest integrity (includes FULL_HOOKS=1 in build flags,
   accurate artifact size and sha256, matches committed manifest).
4. Variant build reproducibility: two builds of the FULL_HOOKS=1 variant give identical hashes.
5. PORT-41 default full build is byte-identical to the PORT-41 output manifest.
6. CreateTask_my hook intercepts in staged core ELF:
   - task_PhySw (0xFC1283AD, FINSIG/VERIFIED) -> mykbd_task
   - task_InitFileModules (0xFC0BD071, FINSIG/VERIFIED) -> init_file_modules_task
   - task_CaptSeq (0xFC06A001, FINSIG) -> capt_seq_task
   - task_FileWrite (0xFC25F3A7, FINSIG) -> filewritetask
   - task_MovieRecord, task_ExpDrv, task_DvlpSeqTask remain stock (disabled).
7. Enabled hooks in build match the enabled=yes rows of docs/PORT42_FULL_HOOKS.md,
   and every enabled row is labelled FINSIG or VERIFIED.
8. capt_seq_task and filewritetask safe trampolines to 0xFC06A001 and 0xFC25F3A7.
9. Card-write suppression compile flags and linker wrap symbols remain active.
10. Candidate invariance: PORT-24..40 candidate builds remain byte-identical.
11. Output manifest committed next to PORT-41 manifest in manifests/ and docs/manifests/.
12. docs/PORT42_FULL_HOOKS.md owner trial plan (order: PORT-41 default first, then variant;
    DISKBOOT SHA-256 check; held press; at most 2 power-ons; check per enabled hook;
    battery-pull recovery; PASS/FAIL notes).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
TOOLCHAIN_GCC = TOOLCHAIN_BIN / "arm-none-eabi-gcc"
TOOLCHAIN_OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"
TOOLCHAIN_NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"
BUILD_SCRIPT = REPO_ROOT / "tools" / "build_port41_full.py"
OUT_DIR = REPO_ROOT / "out" / "port41-full"
WRAPPER_SCRIPT = REPO_ROOT / "scripts" / "gcc_deterministic_wrapper.sh"
MANIFESTS_DIR = REPO_ROOT / "manifests"
DOCS_MANIFESTS_DIR = REPO_ROOT / "docs" / "manifests"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def snapshot_distribution(out_path: Path) -> dict[str, tuple[int, str]]:
    """Capture size and SHA-256 for DISKBOOT.BIN and every file in CHDK/."""
    snapshot: dict[str, tuple[int, str]] = {}
    diskboot = out_path / "DISKBOOT.BIN"
    if diskboot.is_file():
        snapshot["DISKBOOT.BIN"] = (diskboot.stat().st_size, sha256_file(diskboot))
    chdk_dir = out_path / "CHDK"
    if chdk_dir.is_dir():
        for root, dirs, files in os.walk(chdk_dir):
            for f in sorted(files):
                p = Path(root) / f
                rel = str(p.relative_to(out_path))
                snapshot[rel] = (p.stat().st_size, sha256_file(p))
    return snapshot


class TestPort42FullHooksDoc(unittest.TestCase):
    """Static checks on docs/PORT42_FULL_HOOKS.md."""

    def test_doc_table_and_content(self):
        doc_path = REPO_ROOT / "docs" / "PORT42_FULL_HOOKS.md"
        self.assertTrue(doc_path.is_file(), f"Missing {doc_path}")
        text = doc_path.read_text(encoding="utf-8")

        # Table header columns check
        self.assertRegex(text, r"(?i)\|.*hook.*\|.*address.*\|.*label.*\|.*sibling citation.*\|.*enabled")

        # FINSIG confirmed hooks
        for hook in ["task_CaptSeq", "task_FileWrite", "task_InitFileModules", "task_PhySw"]:
            self.assertIn(hook, text, f"{hook} missing in doc table")

        # Addresses
        self.assertIn("0xFC06A001", text)
        self.assertIn("0xFC25F3A7", text)
        self.assertIn("0xFC0BD071", text)
        self.assertIn("0xFC1283AD", text)

        # Labels
        self.assertIn("FINSIG", text)
        self.assertIn("VERIFIED", text)

        # Sibling citations
        self.assertTrue(
            re.search(r"chdk-port/platform/(g7x|g5x)/sub/\w+/\w+\.c:\d+", text),
            "Doc must cite sibling paths with line numbers",
        )

        # Disabled hooks and reasons
        for disabled in ["task_MovieRecord", "task_ExpDrv", "task_DvlpSeqTask"]:
            self.assertIn(disabled, text, f"{disabled} missing in doc table")

    def test_doc_manifest_and_owner_trial_plan(self):
        """Verify docs/PORT42_FULL_HOOKS.md contains output manifest and owner trial plan."""
        doc_path = REPO_ROOT / "docs" / "PORT42_FULL_HOOKS.md"
        self.assertTrue(doc_path.is_file(), f"Missing {doc_path}")
        text = doc_path.read_text(encoding="utf-8")

        # Output manifest details
        self.assertIn("DISKBOOT.BIN", text)
        self.assertIn("124,153", text)
        self.assertIn("eb46aa339bb6557f27d992691f83ceb14cc73962625a44e0f146edde9b886dce", text)
        self.assertIn("port42_full_hooks_manifest.json", text)
        self.assertIn("port41_manifest.json", text)

        # Anchored PORT-41 baseline SHA-256 in doc
        self.assertIn("24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9", text)

        # Owner trial plan: order PORT-41 default before variant
        self.assertRegex(
            text,
            r"(?i)port-41\s+default.*(?:first|before).*variant",
            "Owner trial plan must order PORT-41 default before the variant",
        )

        # DISKBOOT SHA-256 check
        self.assertRegex(text, r"(?i)sha-256.*(?:check|verification)")

        # Held press
        self.assertRegex(text, r"(?i)held\s+press")

        # At most 2 power-ons
        self.assertRegex(text, r"(?i)at\s+most\s+(?:\*\*)?2\s+power-ons")

        # Per-hook validation: observation without capture
        self.assertRegex(text, r"(?i)observation\s+(?:only|without\s+capture)")
        self.assertRegex(text, r"(?i)half-press")
        self.assertNotIn("full shutter press", text.lower())
        self.assertNotIn("card writes suppressed;", text.lower())

        # What to check per enabled hook
        self.assertIn("task_PhySw", text)
        self.assertIn("task_InitFileModules", text)
        self.assertIn("task_CaptSeq", text)
        self.assertIn("task_FileWrite", text)

        # PASS / FAIL criteria: PASS if no hang or crash
        self.assertIn("PASS", text)
        self.assertIn("FAIL", text)
        self.assertRegex(text, r"(?i)no\s+hang\s+or\s+crash")

        # Compile switches named and RAM-only recovery
        self.assertIn("G3X_DISABLE_CARD_WRITES", text)
        self.assertIn("OPT_DISABLE_FILE_WRITES", text)
        self.assertRegex(text, r"(?i)battery-pull\s+recovery")
        self.assertRegex(text, r"(?i)ram-only")

    def test_manifests_mirrored_identical(self):
        """Nit 5: verify that manifests/ and docs/manifests/ copies are byte-identical."""
        for m_name in ["port41_manifest.json", "port42_full_hooks_manifest.json"]:
            primary = MANIFESTS_DIR / m_name
            mirror = DOCS_MANIFESTS_DIR / m_name
            self.assertTrue(primary.is_file(), f"Missing primary manifest: {primary}")
            self.assertTrue(mirror.is_file(), f"Missing mirror manifest: {mirror}")
            self.assertEqual(
                primary.read_bytes(),
                mirror.read_bytes(),
                f"Manifest mirror {mirror} diverged from primary {primary}",
            )


class TestPort42FullHooksExecution(unittest.TestCase):
    """End-to-end execution and binary analysis of FULL_HOOKS=1 build."""

    has_toolchain: bool = False
    build_executed: bool = False
    build_returncode: int = -1
    build_stdout: str = ""
    build_stderr: str = ""

    stage_dir: Path = OUT_DIR / "stage_chdk"
    staged_core_elf: Path = OUT_DIR / "stage_chdk" / "platform" / "g3x" / "sub" / "110c" / "main.elf"
    diskboot: Path = OUT_DIR / "DISKBOOT.BIN"
    p42_manifest: Path = OUT_DIR / "port42_full_hooks_manifest.json"

    @classmethod
    def setUpClass(cls):
        if not TOOLCHAIN_GCC.is_file() or not os.access(TOOLCHAIN_GCC, os.X_OK):
            cls.has_toolchain = False
            return
        cls.has_toolchain = True

        # Run full build with --full-hooks and deterministic wrapper
        env = os.environ.copy()
        if WRAPPER_SCRIPT.is_file() and os.access(WRAPPER_SCRIPT, os.X_OK):
            env["MAKEFLAGS"] = f"CC={WRAPPER_SCRIPT}"

        cmd = ["python3", "-B", str(BUILD_SCRIPT), "--full-hooks"]
        res = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        cls.build_executed = True
        cls.build_returncode = res.returncode
        cls.build_stdout = res.stdout
        cls.build_stderr = res.stderr

    def _require_full_build(self):
        if not self.has_toolchain:
            self.skipTest(f"Pinned toolchain gcc not found at {TOOLCHAIN_GCC}")
        self.assertEqual(
            self.build_returncode,
            0,
            f"build_port41_full.py --full-hooks failed with code {self.build_returncode}:\nSTDOUT:\n{self.build_stdout}\nSTDERR:\n{self.build_stderr}",
        )
        self.assertTrue(
            self.staged_core_elf.is_file(),
            f"Expected staged core ELF {self.staged_core_elf} to exist from full build",
        )

    def test_full_hooks_artifacts_and_manifest(self):
        """Verify FULL_HOOKS variant output matches manifest completely."""
        self._require_full_build()

        # Check DISKBOOT.BIN
        diskboot = self.diskboot
        self.assertTrue(diskboot.is_file(), f"Expected {diskboot} to exist")
        self.assertEqual(diskboot.stat().st_size, 124153)
        self.assertEqual(
            sha256_file(diskboot),
            "eb46aa339bb6557f27d992691f83ceb14cc73962625a44e0f146edde9b886dce",
        )

        # Snapshot actual output directory
        actual = snapshot_distribution(OUT_DIR)

        # Verify against both manifest locations (primary manifests/ and mirror docs/manifests/)
        for manifest_dir in [MANIFESTS_DIR, DOCS_MANIFESTS_DIR]:
            m_path = manifest_dir / "port42_full_hooks_manifest.json"
            self.assertTrue(m_path.is_file(), f"Expected {m_path} to exist")
            with open(m_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            self.assertIn("FULL_HOOKS=1", manifest["build"]["flags"])

            # Construct complete expected file set from manifest
            expected: dict[str, tuple[int, str]] = {
                "DISKBOOT.BIN": (
                    manifest["artifacts"]["DISKBOOT.BIN"]["size"],
                    manifest["artifacts"]["DISKBOOT.BIN"]["sha256"],
                )
            }
            for rel, info in manifest["artifacts"]["chdk_files"].items():
                expected[rel] = (info["size"], info["sha256"])

            # Full file set comparison: paths, sizes and SHA-256 hashes equal
            self.assertEqual(
                set(actual.keys()),
                set(expected.keys()),
                f"Variant output file set does not match manifest in {m_path}",
            )
            self.assertEqual(
                actual,
                expected,
                f"Variant output file sizes or hashes do not match manifest in {m_path}",
            )

    def test_variant_build_reproducibility(self):
        """Requirement (a): FULL_HOOKS=1 variant builds reproducibly (two builds give identical hashes)."""
        self._require_full_build()

        env = os.environ.copy()
        if WRAPPER_SCRIPT.is_file() and os.access(WRAPPER_SCRIPT, os.X_OK):
            env["MAKEFLAGS"] = f"CC={WRAPPER_SCRIPT}"

        # 1. Snapshot the variant built in setUpClass
        snapshot1 = snapshot_distribution(OUT_DIR)
        self.assertIn("DISKBOOT.BIN", snapshot1)
        self.assertGreaterEqual(len(snapshot1), 200)

        # 2. Rebuild into a clean output directory
        shutil.rmtree(OUT_DIR, ignore_errors=True)
        OUT_DIR.mkdir(parents=True, exist_ok=True)

        cmd = ["python3", "-B", str(BUILD_SCRIPT), "--full-hooks"]
        res = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        self.assertEqual(res.returncode, 0, f"Rebuild failed: {res.stderr}")

        # 3. Snapshot again
        snapshot2 = snapshot_distribution(OUT_DIR)

        # 4. Assert that the two snapshots are equal: the same file set, sizes and hashes
        self.assertEqual(
            set(snapshot1.keys()),
            set(snapshot2.keys()),
            "Variant rebuild produced different file sets",
        )
        self.assertEqual(
            snapshot1,
            snapshot2,
            "Variant rebuild produced different file sizes or SHA-256 hashes",
        )

        # 5. Only then compare the result against the committed variant manifest
        m_path = MANIFESTS_DIR / "port42_full_hooks_manifest.json"
        self.assertTrue(m_path.is_file(), f"Missing variant manifest: {m_path}")
        with open(m_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        expected: dict[str, tuple[int, str]] = {
            "DISKBOOT.BIN": (
                manifest["artifacts"]["DISKBOOT.BIN"]["size"],
                manifest["artifacts"]["DISKBOOT.BIN"]["sha256"],
            )
        }
        for rel, info in manifest["artifacts"]["chdk_files"].items():
            expected[rel] = (info["size"], info["sha256"])

        self.assertEqual(
            set(snapshot2.keys()),
            set(expected.keys()),
            "Reproducible build files do not match manifest file set",
        )
        self.assertEqual(
            snapshot2,
            expected,
            "Reproducible build sizes or hashes do not match manifest",
        )

    def test_port41_default_build_byte_identical_to_manifest(self):
        """Requirement (b): PORT-41 default full build is byte-identical to the PORT-41 output manifest."""
        self._require_full_build()

        manifest_path = MANIFESTS_DIR / "port41_manifest.json"
        self.assertTrue(manifest_path.is_file(), f"Missing {manifest_path}")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        expected_diskboot = manifest["artifacts"]["DISKBOOT.BIN"]
        expected_sha = expected_diskboot["sha256"]
        expected_size = expected_diskboot["size"]

        # Assert manifest itself anchors the recorded PORT-41 baseline
        recorded_baseline_sha = "24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9"
        self.assertEqual(
            expected_sha,
            recorded_baseline_sha,
            f"port41_manifest.json DISKBOOT SHA-256 must match recorded baseline {recorded_baseline_sha}",
        )
        self.assertEqual(expected_size, 124097)

        # Clean output directory before building default build
        shutil.rmtree(OUT_DIR, ignore_errors=True)
        OUT_DIR.mkdir(parents=True, exist_ok=True)

        # Run PORT-41 default full build (no --full-hooks)
        env = os.environ.copy()
        if WRAPPER_SCRIPT.is_file() and os.access(WRAPPER_SCRIPT, os.X_OK):
            env["MAKEFLAGS"] = f"CC={WRAPPER_SCRIPT}"

        cmd = ["python3", "-B", str(BUILD_SCRIPT)]
        res = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        self.assertEqual(res.returncode, 0, f"PORT-41 default build failed: {res.stderr}")

        # Snapshot default build
        actual_default = snapshot_distribution(OUT_DIR)

        # Complete manifest comparison: path set equal, sizes equal, and SHA-256 equal
        expected_default: dict[str, tuple[int, str]] = {
            "DISKBOOT.BIN": (expected_size, expected_sha)
        }
        for rel, info in manifest["artifacts"]["chdk_files"].items():
            expected_default[rel] = (info["size"], info["sha256"])

        self.assertEqual(
            set(actual_default.keys()),
            set(expected_default.keys()),
            "PORT-41 default build output file set does not match manifest",
        )
        self.assertEqual(
            actual_default,
            expected_default,
            "PORT-41 default build output sizes or hashes do not match manifest",
        )

        # Explicit anchor assertion: DISKBOOT.BIN matches recorded PORT-41 baseline
        self.assertEqual(
            actual_default["DISKBOOT.BIN"][1],
            recorded_baseline_sha,
            "PORT-41 default DISKBOOT SHA-256 diverged from recorded baseline in docs/PORT41_FULL_BUILD.md:146",
        )

        # Restore FULL_HOOKS build for remaining tests
        subprocess.run(
            ["python3", "-B", str(BUILD_SCRIPT), "--full-hooks"],
            cwd=str(REPO_ROOT),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            env=env,
            check=True,
        )

    def test_enabled_hooks_match_doc_table_and_labels(self):
        """Requirement (d): hooks enabled in the build match enabled=yes rows in doc table, and every enabled row is FINSIG or VERIFIED."""
        self._require_full_build()

        doc_path = REPO_ROOT / "docs" / "PORT42_FULL_HOOKS.md"
        self.assertTrue(doc_path.is_file(), f"Missing {doc_path}")
        text = doc_path.read_text(encoding="utf-8")

        # Parse table rows: | Hook | Address | Label | Sibling Citation | Enabled (yes/no) | Notes |
        row_regex = re.compile(r"^\|\s*`?(\w+)`?\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*(yes|no)\s*\|(.*)$", re.M)
        rows = row_regex.findall(text)
        self.assertGreaterEqual(len(rows), 8, "Expected at least 8 evaluated hooks in doc table")

        enabled_in_doc = []
        disabled_in_doc = []
        for hook_name, addr, label, sib, enabled, notes in rows:
            label_clean = label.strip()
            if enabled.strip().lower() == "yes":
                enabled_in_doc.append(hook_name.strip())
                # Every enabled hook MUST be labelled FINSIG or VERIFIED
                self.assertTrue(
                    "FINSIG" in label_clean or "VERIFIED" in label_clean,
                    f"Enabled hook {hook_name} has invalid label '{label_clean}'; must be FINSIG or VERIFIED",
                )
            else:
                disabled_in_doc.append(hook_name.strip())

        # Check disassembly / symbol table of staged_core_elf
        objdump_res = subprocess.run(
            [str(TOOLCHAIN_OBJDUMP), "-d", str(self.staged_core_elf)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        core_disasm = objdump_res.stdout
        core_disasm_lower = core_disasm.lower()

        # Enabled hooks mapping: hook_name -> expected intercept symbol
        expected_intercept_symbols = {
            "task_PhySw": "<mykbd_task>",
            "task_InitFileModules": "<init_file_modules_task>",
            "task_CaptSeq": "<capt_seq_task>",
            "task_FileWrite": "<filewritetask>",
        }

        # Verify that all enabled hooks match expected set
        self.assertEqual(
            set(enabled_in_doc),
            set(expected_intercept_symbols.keys()),
            f"Doc enabled hooks {enabled_in_doc} do not match expected {list(expected_intercept_symbols.keys())}",
        )

        # Verify every enabled hook is present and hooked in the build output
        for hook, sym in expected_intercept_symbols.items():
            self.assertIn(
                sym,
                core_disasm,
                f"Enabled hook {hook} interception symbol {sym} missing in built core binary",
            )

        # Verify every disabled hook is NOT hooked in CreateTask_my
        ct_idx = core_disasm.find("<CreateTask_my>:")
        self.assertGreater(ct_idx, 0, "CreateTask_my function missing in disasm")
        ct_end_idx = core_disasm.find("exitHook>:", ct_idx)
        ct_chunk = core_disasm[ct_idx : ct_end_idx + 200].lower()

        for disabled_hook in disabled_in_doc:
            # The literal hook address for disabled tasks should not be compared against r3 in CreateTask_my
            # E.g. task_MovieRecord = 0xFC09AC19
            if disabled_hook == "task_MovieRecord":
                self.assertNotIn("fc09ac19", ct_chunk, "Disabled hook task_MovieRecord found in CreateTask_my")
            elif disabled_hook == "task_ExpDrv":
                self.assertNotIn("fc2c136f", ct_chunk, "Disabled hook task_ExpDrv found in CreateTask_my")
            elif disabled_hook == "task_DvlpSeqTask":
                self.assertNotIn("fc07b637", ct_chunk, "Disabled hook task_DvlpSeqTask found in CreateTask_my")

    def test_createtask_interceptions(self):
        self._require_full_build()

        objdump_res = subprocess.run(
            [str(TOOLCHAIN_OBJDUMP), "-d", str(self.staged_core_elf)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        core_disasm = objdump_res.stdout
        core_disasm_lower = core_disasm.lower()

        # 1. CreateTask_my symbol presence
        self.assertIn("<CreateTask_my>:", core_disasm)

        # 2. task_CaptSeq intercept (0xFC06A001)
        self.assertIn("fc06a001", core_disasm_lower, "task_CaptSeq (0xFC06A001) literal missing in core")
        self.assertIn("<capt_seq_task>", core_disasm, "capt_seq_task hook missing in core")

        # 3. task_FileWrite intercept (0xFC25F3A7)
        self.assertIn("fc25f3a7", core_disasm_lower, "task_FileWrite (0xFC25F3A7) literal missing in core")
        self.assertIn("<filewritetask>", core_disasm, "filewritetask hook missing in core")

        # 4. task_PhySw intercept (0xFC1283AD)
        self.assertIn("fc1283ad", core_disasm_lower, "task_PhySw (0xFC1283AD) literal missing in core")
        self.assertIn("<mykbd_task>", core_disasm, "mykbd_task missing in core")

        # 5. task_InitFileModules intercept (0xFC0BD071)
        self.assertIn("fc0bd071", core_disasm_lower, "task_InitFileModules (0xFC0BD071) literal missing in core")
        self.assertIn("<init_file_modules_task>", core_disasm, "init_file_modules_task missing in core")

        # Disassemble capt_seq_task and filewritetask to verify safe branch
        cs_idx = core_disasm.find("<capt_seq_task>:")
        self.assertGreater(cs_idx, 0)
        cs_chunk = core_disasm[cs_idx : cs_idx + 200].lower()
        self.assertIn("fc06a001", cs_chunk, "capt_seq_task must branch to 0xFC06A001")

        fw_idx = core_disasm.find("<filewritetask>:")
        self.assertGreater(fw_idx, 0)
        fw_chunk = core_disasm[fw_idx : fw_idx + 200].lower()
        self.assertIn("fc25f3a7", fw_chunk, "filewritetask must branch to 0xFC25F3A7")

    def test_card_writes_stay_off_with_full_hooks(self):
        self._require_full_build()

        nm_res = subprocess.run(
            [str(TOOLCHAIN_NM), "-n", str(self.staged_core_elf)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        nm_out = nm_res.stdout

        for sym in [
            "__wrap_open",
            "__wrap_fopen",
            "__wrap_creat",
            "__wrap_write",
            "__wrap_fwrite",
            "__wrap_mkdir",
            "__wrap_remove",
            "__wrap_rename",
            "__wrap_conf_save",
            "__wrap_save_params_values",
        ]:
            self.assertIn(sym, nm_out, f"Linker wrap symbol {sym} missing in core binary")

        # Staged makefile checks
        staged_makefile = self.stage_dir / "platform" / "g3x" / "sub" / "110c" / "Makefile"
        self.assertTrue(staged_makefile.is_file())
        make_text = staged_makefile.read_text(encoding="utf-8")
        self.assertIn("-DG3X_DISABLE_CARD_WRITES=1", make_text)
        self.assertIn("-DOPT_DISABLE_FILE_WRITES=1", make_text)

    def test_candidate_invariance_under_full_hooks(self):
        """Requirement (c): Verify that PORT-24..40 candidates remain 100% byte-identical."""
        if not self.has_toolchain:
            self.skipTest(f"Pinned toolchain gcc not found at {TOOLCHAIN_GCC}")

        import tempfile
        import sys

        scripts_dir = REPO_ROOT / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from build_candidate_gui3 import build_candidate

        pinned_candidates = [
            ("default", {"ladder": False, "poweron_fix": False, "resident": False}, "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136", 118001),
            ("gui4", {"gui4": True}, "14456b08fca82758262c26ad6105f784ebacaa080b7a059a622ded5a8d505fdd", 102241),
            ("gui5", {"gui5": True}, "dd96357c050cf3b9116dcf089a731ef159477b505351f46436f983fdbf090b64", 102209),
            ("gui5_shortpress", {"gui5": True, "shortpress": True}, "86e12a2cfe792a8901fa2e0ec5a98f019290593e35d5c4c2e66fd3e073f16ff1", 102369),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            for name, kwargs, expected_sha, expected_size in pinned_candidates:
                cand_dir = os.path.join(tmpdir, name)
                res = build_candidate(out_dir=cand_dir, **kwargs)
                diskboot = Path(cand_dir) / "DISKBOOT.BIN"
                self.assertTrue(diskboot.is_file(), f"DISKBOOT.BIN for {name} candidate does not exist")
                self.assertEqual(res["diskboot_size"], expected_size, f"Size mismatch for {name} candidate build")
                self.assertEqual(res["diskboot_sha256"], expected_sha, f"SHA-256 mismatch for {name} candidate build")


if __name__ == "__main__":
    unittest.main()
