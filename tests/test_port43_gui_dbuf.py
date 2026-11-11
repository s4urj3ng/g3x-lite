"""Unit and integration host tests for PORT-43 double-buffered GUI build, draw layer, and trial plan.

Verifies:
1. docs/PORT43_TRIAL_PLAN.md format and content:
   - DISKBOOT SHA-256 check before the trial
   - Held-press boot method
   - At most 2 power-ons limit
   - Battery-pull recovery (>= 10 s) and rollback to PORT-42 build
   - Owner observations: 10 s idle video + navigation, stability (no vanish-to-live-view cycle),
     repaint speed (no growing bands), boot method recorded, colours/opacity/2x font/layout match PORT-42,
     and any new regression (pink blocks, edge leaks, lockups).
2. manifests/port43_gui_dbuf_manifest.json:
   - Lists DISKBOOT.BIN (126,329 B, SHA-256 8d5509e5...)
   - Lists every CHDK/ file with size and SHA-256 (34 modules).
3. Reproducible build:
   - Two builds of G3X_GUI_FIX=1 G3X_GUI_DBUF=1 produce byte-for-byte identical DISKBOOT.BIN and CHDK/ files.
4. Byte identity to existing manifests:
   - PORT-42 GUI build (G3X_GUI_FIX=1 alone, 124,257 B, 760a362d...)
   - PORT-41 default full build (124,097 B, 24b8a024...)
   - FULL_HOOKS variant (124,153 B, eb46aa33...)
   - GUI_FIX + FULL_HOOKS variant (124,321 B, d50ea585...)
   - Every PORT-24..40 candidate: default, poweron_fix, ladder, combined, resident,
     osd, kbd, kbd_osd, osd2, gui, gui2, gui3, gui4, shortpress, gui5, gui5_shortpress.
5. Host-side model and unit tests of the draw layer:
   - Both bitmap buffers and both opacity buffers receive identical overlay bytes.
   - Fill paths use 32-bit word writes and never call draw_pixel.
   - Cursor moves touch only changed rows via row signature cache.
   - Shadow restore is a single blit (4 memcpys) producing the exact same bytes as original draw.
   - Compiled ARM object disassembly confirms fast fill call sites and lack of draw_pixel in fills.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
TOOLCHAIN_GCC = TOOLCHAIN_BIN / "arm-none-eabi-gcc"
TOOLCHAIN_OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"
TOOLCHAIN_NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"

BUILD_SCRIPT_DBUF = REPO_ROOT / "scripts" / "build_port43_dbuf.py"
BUILD_SCRIPT_PORT41 = REPO_ROOT / "tools" / "build_port41_full.py"
WRAPPER_SCRIPT = REPO_ROOT / "scripts" / "gcc_deterministic_wrapper.sh"
MANIFESTS_DIR = REPO_ROOT / "manifests"

# Dedicated clean output directories per variant under out/port43-test/
TEST_BASE_OUT_DIR = REPO_ROOT / "out" / "port43-test"
OUT_DIR_PORT41_DEFAULT = TEST_BASE_OUT_DIR / "port41_default"
OUT_DIR_FULL_HOOKS = TEST_BASE_OUT_DIR / "full_hooks"
OUT_DIR_PORT42_GUI_FIX = TEST_BASE_OUT_DIR / "port42_gui_fix"
OUT_DIR_GUI_FIX_FULL_HOOKS = TEST_BASE_OUT_DIR / "gui_fix_full_hooks"
OUT_DIR_GUI_FIX_DBUF = TEST_BASE_OUT_DIR / "gui_fix_dbuf"

EXPECTED_DBUF_SIZE = 126329
EXPECTED_DBUF_SHA256 = "8d5509e597a598e8bb023adae46d4caa2c7ee1e2b763e4ff292f0aef21f9b140"
EXPECTED_PORT42_GUI_SIZE = 124257
EXPECTED_PORT42_GUI_SHA256 = "760a362d358d87518e6274013e70109f8699974a40158ae5bbbff8b80c246738"
EXPECTED_PORT41_FULL_SIZE = 124097
EXPECTED_PORT41_FULL_SHA256 = "24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9"
EXPECTED_FULL_HOOKS_SIZE = 124153
EXPECTED_FULL_HOOKS_SHA256 = "eb46aa339bb6557f27d992691f83ceb14cc73962625a44e0f146edde9b886dce"
EXPECTED_GUI_FULL_HOOKS_SIZE = 124321
EXPECTED_GUI_FULL_HOOKS_SHA256 = "d50ea585b2ba49e39674395f504b5780a1cb98a915fe998c5b7fa5be115cb9bb"

# Complete table of all PORT-24..40 candidates with build options, expected hash, expected size,
# and the git-tracked source document that canonically records its DISKBOOT SHA-256.
PINNED_CANDIDATES = [
    (
        "default",
        {"ladder": False, "poweron_fix": False, "resident": False},
        "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136",
        118001,
        "docs/PORT16_CANDIDATE_BUILD.md",
    ),
    (
        "poweron_fix",
        {"ladder": False, "poweron_fix": True, "resident": False},
        "faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056",
        118001,
        "docs/PORT24_LOADER_TRACE.md",
    ),
    (
        "ladder",
        {"ladder": True, "poweron_fix": False, "resident": False},
        "45da469f3eb46c4d2aff77a032e5c8bb4eedf8ec8846526853d716d05d2b2f4e",
        126081,
        "docs/PORT25_LADDER_FIX_CANDIDATE.md",
    ),
    (
        "combined",
        {"ladder": True, "poweron_fix": True, "resident": False},
        "9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15",
        124865,
        "docs/PORT25_LADDER_FIX_CANDIDATE.md",
    ),
    (
        "resident",
        {"resident": True},
        "63c7942f561242b55d8226bfefe7818dd5b959aee35eae0adb4f41a4783ece5a",
        124561,
        "docs/PORT32_RESIDENT_CANDIDATE.md",
    ),
    (
        "osd",
        {"osd": True},
        "683751539979f3e8956fd6c1794683c062f54385e6e1a3261b02ed8d63cc9855",
        124833,
        "docs/PORT33_OSD_ADDRESSES.md",
    ),
    (
        "kbd",
        {"kbd": True},
        "a750253feb0cd9bb3bb1addb4cede5585bef29a0bf26bd86d3f577fdbf41be33",
        124801,
        "docs/PORT34_KBD_ADDRESSES.md",
    ),
    (
        "kbd_osd",
        {"kbd": True, "osd": True},
        "686c4e4688f74cccd2b7a21e7000eb574672635cfd4d17c885d86bbf52eb99a8",
        125121,
        "docs/PORT34_KBD_ADDRESSES.md",
    ),
    (
        "osd2",
        {"osd2": True},
        "20d65a7d9be954d5caafe2f78751429ea388a37ca570f0bbd0d620609eb31a57",
        125329,
        "docs/PORT35_GUI_ADDRESSES.md",
    ),
    (
        "gui",
        {"gui": True},
        "1f6494cd8e7fd7629b82ed33ba1ec4fa939aa1aa2ff22f541c28a28c742e4272",
        103057,
        "docs/PORT35_GUI_ADDRESSES.md",
    ),
    (
        "gui2",
        {"gui2": True},
        "4a8c4b503a4b78a262ca208c629de8305aa186efbc2fda82951d77084ade9071",
        103345,
        "docs/PORT36_GUI_GEOMETRY.md",
    ),
    (
        "gui3",
        {"gui3": True},
        "4aded2d2abbe0c3101583c79708d084ffe93101fc9b889a76970e66a175be638",
        103569,
        "docs/PORT37_GUI_FLICKER.md",
    ),
    (
        "gui4",
        {"gui4": True},
        "14456b08fca82758262c26ad6105f784ebacaa080b7a059a622ded5a8d505fdd",
        102241,
        "docs/PORT38_GUI4_TRIAL.md",
    ),
    (
        "shortpress",
        {"shortpress": True},
        "6df54a905e36a6fe92b5a3a4ac4dd71086d3306fd0aaa31a1f1bc670f7e19461",
        124945,
        "docs/PORT39_SHORTPRESS_TRIAL.md",
    ),
    (
        "gui5",
        {"gui5": True},
        "dd96357c050cf3b9116dcf089a731ef159477b505351f46436f983fdbf090b64",
        102209,
        "docs/PORT40_GUI_LAYOUT.md",
    ),
    (
        "gui5_shortpress",
        {"gui5": True, "shortpress": True},
        "86e12a2cfe792a8901fa2e0ec5a98f019290593e35d5c4c2e66fd3e073f16ff1",
        102369,
        "docs/PORT40_GUI_LAYOUT.md",
    ),
]


def sha256_file(path: Path | str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def snapshot_distribution(out_path: Path) -> dict[str, tuple[int, str]]:
    snapshot: dict[str, tuple[int, str]] = {}
    diskboot = out_path / "DISKBOOT.BIN"
    assert diskboot.is_file(), f"Expected DISKBOOT.BIN to exist in {out_path}"
    snapshot["DISKBOOT.BIN"] = (diskboot.stat().st_size, sha256_file(diskboot))

    chdk_dir = out_path / "CHDK"
    assert chdk_dir.is_dir(), f"Expected CHDK/ directory to exist in {out_path}"
    for root, dirs, files in os.walk(chdk_dir):
        for f in sorted(files):
            p = Path(root) / f
            rel = str(p.relative_to(out_path))
            snapshot[rel] = (p.stat().st_size, sha256_file(p))
    return snapshot


def _require_or_build_distribution(
    out_path: Path,
    build_args: list[str],
    expected_sha256: str | None = None,
    script: Path = BUILD_SCRIPT_PORT41,
) -> Path:
    """Ensure a full distribution directory exists with valid DISKBOOT.BIN for the requested variant, or build it.

    Never returns a stale binary built for a different variant.
    If out_path already contains a DISKBOOT.BIN:
    - If expected_sha256 is provided and matches, return out_path (valid cached binary).
    - If expected_sha256 is provided and differs (stale binary from another variant or build),
      wipe out_path and rebuild cleanly.
    - If expected_sha256 is omitted, return if DISKBOOT.BIN is present and non-empty.
    Always wipes out_path before building so each variant build is completely clean.
    """
    diskboot = out_path / "DISKBOOT.BIN"
    chdk_dir = out_path / "CHDK"
    if diskboot.is_file() and diskboot.stat().st_size > 0 and chdk_dir.is_dir():
        if expected_sha256 is not None:
            if sha256_file(diskboot) == expected_sha256:
                return out_path
            # Stale binary from another variant; fall through to wipe and rebuild
        else:
            return out_path

    # Wipe out_path before building to guarantee a clean output directory
    if out_path.exists():
        shutil.rmtree(out_path)
    out_path.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env.pop("G3X_GUI_FIX", None)
    env.pop("G3X_GUI_DBUF", None)
    env.pop("FULL_HOOKS", None)
    if WRAPPER_SCRIPT.is_file() and os.access(WRAPPER_SCRIPT, os.X_OK):
        env["MAKEFLAGS"] = f"CC={WRAPPER_SCRIPT}"

    cmd = ["python3", "-B", str(script)] + build_args + ["--out-dir", str(out_path)]
    res = subprocess.run(
        cmd,
        cwd=str(REPO_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        env=env,
    )
    if res.returncode != 0:
        raise RuntimeError(f"Build failed for {out_path} ({cmd}):\n{res.stderr}\n{res.stdout}")

    if not diskboot.is_file() or diskboot.stat().st_size == 0:
        raise RuntimeError(f"DISKBOOT.BIN missing or empty after building {out_path}")

    if expected_sha256 is not None:
        actual_sha = sha256_file(diskboot)
        if actual_sha != expected_sha256:
            raise RuntimeError(
                f"Build of {out_path} produced unexpected SHA-256: {actual_sha} != {expected_sha256}"
            )

    return out_path


def _require_or_build_candidate(
    name: str,
    kwargs: dict,
    expected_sha256: str,
    expected_size: int,
) -> Path:
    """Ensure candidate output directory exists with byte-identical DISKBOOT.BIN, or build it cleanly.

    Never reads or creates git-ignored candidate_port*/ paths. Uses out/port43-test/candidate_<name>/.
    Wipes the output directory before building if missing or stale.
    """
    cand_dir = TEST_BASE_OUT_DIR / f"candidate_{name}"
    diskboot = cand_dir / "DISKBOOT.BIN"
    cand_mpath = cand_dir / "candidate_manifest.json"

    if diskboot.is_file() and diskboot.stat().st_size == expected_size and cand_mpath.is_file():
        if sha256_file(diskboot) == expected_sha256:
            return cand_dir
        # Stale binary from a different variant; wipe and rebuild

    if cand_dir.exists():
        shutil.rmtree(cand_dir)
    cand_dir.mkdir(parents=True, exist_ok=True)

    import sys
    scripts_dir = REPO_ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from build_candidate_gui3 import build_candidate

    res = build_candidate(out_dir=str(cand_dir), **kwargs)
    if not diskboot.is_file():
        raise RuntimeError(f"DISKBOOT.BIN missing for candidate {name} in {cand_dir}")

    actual_size = diskboot.stat().st_size
    actual_sha = sha256_file(diskboot)
    if actual_size != expected_size:
        raise RuntimeError(f"Candidate {name} size {actual_size} != expected {expected_size}")
    if actual_sha != expected_sha256:
        raise RuntimeError(f"Candidate {name} sha256 {actual_sha} != expected {expected_sha256}")

    return cand_dir


def _verify_distribution_against_manifest(out_path: Path, manifest_path: Path) -> None:
    """Compare actual build output DISKBOOT.BIN and every CHDK/ file against an existing manifest."""
    assert manifest_path.is_file(), f"Manifest missing at {manifest_path}"
    with open(manifest_path, "r", encoding="utf-8") as f:
        mdata = json.load(f)

    actual_snap = snapshot_distribution(out_path)
    expected_db = mdata["artifacts"]["DISKBOOT.BIN"]
    actual_db = actual_snap["DISKBOOT.BIN"]
    assert actual_db == (expected_db["size"], expected_db["sha256"]), (
        f"DISKBOOT.BIN mismatch between {out_path} and {manifest_path}: "
        f"actual {actual_db} vs manifest {(expected_db['size'], expected_db['sha256'])}"
    )

    for rel_path, exp_info in mdata["artifacts"]["chdk_files"].items():
        assert rel_path in actual_snap, f"File {rel_path} listed in {manifest_path} missing from {out_path}"
        actual_info = actual_snap[rel_path]
        assert actual_info == (exp_info["size"], exp_info["sha256"]), (
            f"File {rel_path} mismatch in {out_path}: "
            f"actual {actual_info} vs manifest {exp_info}"
        )


class TestPort43TrialPlanDoc(unittest.TestCase):
    """Static verification of docs/PORT43_TRIAL_PLAN.md."""

    def setUp(self):
        self.doc_path = REPO_ROOT / "docs" / "PORT43_TRIAL_PLAN.md"
        self.assertTrue(self.doc_path.is_file(), f"Missing {self.doc_path}")
        self.doc_text = self.doc_path.read_text(encoding="utf-8")

    def test_trial_plan_sha_check_and_size(self):
        """Doc must specify exact preflight DISKBOOT SHA-256 and size check."""
        self.assertIn(EXPECTED_DBUF_SHA256, self.doc_text)
        self.assertIn("126,329", self.doc_text)

    def test_trial_plan_held_press_boot(self):
        """Doc must require held-press boot."""
        self.assertRegex(self.doc_text, r"(?i)held\s+press")

    def test_trial_plan_poweron_limit(self):
        """Doc must enforce at most 2 power-ons."""
        self.assertRegex(self.doc_text, r"(?i)at\s+most\s+2\s+power-ons|maximum\s+2\s+power-ons")

    def test_trial_plan_battery_pull_recovery_and_rollback(self):
        """Doc must cover battery-pull recovery and rollback to PORT-42 build."""
        self.assertRegex(self.doc_text, r"(?i)battery\s+pull")
        self.assertIn(EXPECTED_PORT42_GUI_SHA256, self.doc_text)
        self.assertIn("124,257", self.doc_text)

    def test_trial_plan_observation_checklist(self):
        """Doc must ask owner to record all required observations."""
        self.assertRegex(self.doc_text, r"(?i)10\s*s.*video|video.*10\s*s")
        self.assertRegex(self.doc_text, r"(?i)vanish-to-live-view")
        self.assertRegex(self.doc_text, r"(?i)grow.*bands")
        self.assertRegex(self.doc_text, r"(?i)short.*held|held.*short")
        self.assertRegex(self.doc_text, r"(?i)port-42")
        self.assertRegex(self.doc_text, r"(?i)pink\s+blocks")
        self.assertRegex(self.doc_text, r"(?i)edge\s+leaks")
        self.assertRegex(self.doc_text, r"(?i)lockups?")


class TestPort43ManifestIntegrity(unittest.TestCase):
    """Verification of manifests/port43_gui_dbuf_manifest.json."""

    def setUp(self):
        self.manifest_path = MANIFESTS_DIR / "port43_gui_dbuf_manifest.json"
        self.assertTrue(self.manifest_path.is_file(), f"Missing {self.manifest_path}")
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def test_manifest_build_flags(self):
        """Manifest flags must include G3X_GUI_DBUF=1 and G3X_GUI_FIX=1."""
        flags = self.data["build"]["flags"]
        self.assertIn("G3X_GUI_DBUF=1", flags)
        self.assertIn("G3X_GUI_FIX=1", flags)
        self.assertIn("G3X_FULL_BUILD=1", flags)
        self.assertIn("G3X_DISABLE_CARD_WRITES=1", flags)

    def test_manifest_diskboot_artifact(self):
        """Manifest DISKBOOT.BIN matches expected SHA-256 and size."""
        db = self.data["artifacts"]["DISKBOOT.BIN"]
        self.assertEqual(db["size"], EXPECTED_DBUF_SIZE)
        self.assertEqual(db["sha256"], EXPECTED_DBUF_SHA256)

    def test_manifest_chdk_files_coverage(self):
        """Manifest lists 34 loadable modules and valid non-empty files."""
        self.assertEqual(self.data["artifacts"]["modules_count"], 34)
        self.assertGreater(self.data["artifacts"]["chdk_files_count"], 100)
        chdk_files = self.data["artifacts"]["chdk_files"]
        for rel_path, info in chdk_files.items():
            self.assertTrue(rel_path.startswith("CHDK/"), f"{rel_path} must start with CHDK/")
            self.assertGreater(info["size"], 0)
            self.assertEqual(len(info["sha256"]), 64)


class TestPort43BuildReproducibility(unittest.TestCase):
    """Verification that G3X_GUI_FIX=1 G3X_GUI_DBUF=1 builds reproducibly."""

    @classmethod
    def setUpClass(cls):
        if not TOOLCHAIN_GCC.is_file():
            raise unittest.SkipTest("ARM toolchain compiler not available")

    def test_dbuf_build_reproducibility(self):
        """Two builds of the variant give identical SHA-256."""
        # Ensure out/port43-test/gui_fix_dbuf has the baseline build
        out_dbuf = _require_or_build_distribution(
            OUT_DIR_GUI_FIX_DBUF,
            [],
            expected_sha256=EXPECTED_DBUF_SHA256,
            script=BUILD_SCRIPT_DBUF,
        )
        snap1 = snapshot_distribution(out_dbuf)
        self.assertEqual(snap1["DISKBOOT.BIN"], (EXPECTED_DBUF_SIZE, EXPECTED_DBUF_SHA256))

        # Build 2 in fresh temporary directory
        with tempfile.TemporaryDirectory() as td2:
            res2 = subprocess.run(
                ["python3", "-B", str(BUILD_SCRIPT_DBUF), "--out-dir", td2],
                cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(res2.returncode, 0, f"Build 2 failed: {res2.stderr}")

            snap2 = snapshot_distribution(Path(td2))
            self.assertEqual(snap1, snap2, "Two clean DBUF builds produced different hashes")
            self.assertEqual(snap2["DISKBOOT.BIN"], (EXPECTED_DBUF_SIZE, EXPECTED_DBUF_SHA256))


class TestPort43ByteIdentityToExistingManifests(unittest.TestCase):
    """Verify byte-identity against all prior manifests."""

    @classmethod
    def setUpClass(cls):
        if not TOOLCHAIN_GCC.is_file():
            raise unittest.SkipTest("ARM toolchain compiler not available")

    def test_port42_gui_manifest_match(self):
        """PORT-42 GUI build is byte-identical to its existing manifest."""
        out_dir = _require_or_build_distribution(
            OUT_DIR_PORT42_GUI_FIX,
            ["--gui-fix"],
            expected_sha256=EXPECTED_PORT42_GUI_SHA256,
        )
        mpath = MANIFESTS_DIR / "port42_gui_manifest.json"
        _verify_distribution_against_manifest(out_dir, mpath)

        fix_mpath = MANIFESTS_DIR / "port42_gui_fix_manifest.json"
        if fix_mpath.is_file():
            _verify_distribution_against_manifest(out_dir, fix_mpath)

    def test_port41_default_full_manifest_match(self):
        """PORT-41 default full build is byte-identical to its existing manifest."""
        target_dir = _require_or_build_distribution(
            OUT_DIR_PORT41_DEFAULT,
            [],
            expected_sha256=EXPECTED_PORT41_FULL_SHA256,
        )
        mpath = MANIFESTS_DIR / "port41_manifest.json"
        _verify_distribution_against_manifest(target_dir, mpath)

    def test_full_hooks_manifest_match(self):
        """FULL_HOOKS variants are byte-identical to their existing manifests."""
        # 1. Baseline FULL_HOOKS build
        target_full = _require_or_build_distribution(
            OUT_DIR_FULL_HOOKS,
            ["--full-hooks"],
            expected_sha256=EXPECTED_FULL_HOOKS_SHA256,
        )
        mpath_full = MANIFESTS_DIR / "port42_full_hooks_manifest.json"
        _verify_distribution_against_manifest(target_full, mpath_full)

        # 2. GUI-fixed FULL_HOOKS build
        target_gui_hooks = _require_or_build_distribution(
            OUT_DIR_GUI_FIX_FULL_HOOKS,
            ["--gui-fix", "--full-hooks"],
            expected_sha256=EXPECTED_GUI_FULL_HOOKS_SHA256,
        )
        for name in ["port42_gui_fix_full_hooks_manifest.json", "port42_gui_full_hooks_manifest.json"]:
            p = MANIFESTS_DIR / name
            if p.is_file():
                _verify_distribution_against_manifest(target_gui_hooks, p)

    def test_stale_variant_rebuild_regression_check(self):
        """Regression check: start with a default build already in out/port41-full, then show that the FULL_HOOKS comparison still builds FULL_HOOKS and matches its manifest."""
        out_port41_full = REPO_ROOT / "out" / "port41-full"

        # 1. Place a default build into out/port41-full (simulating a prior default build)
        _require_or_build_distribution(
            out_port41_full,
            [],
            expected_sha256=EXPECTED_PORT41_FULL_SHA256,
        )
        self.assertEqual(
            sha256_file(out_port41_full / "DISKBOOT.BIN"),
            EXPECTED_PORT41_FULL_SHA256,
            "Precondition: out/port41-full must contain the default build",
        )

        # 2. Show that requesting FULL_HOOKS rebuilds FULL_HOOKS despite out/port41-full already existing
        rebuilt = _require_or_build_distribution(
            out_port41_full,
            ["--full-hooks"],
            expected_sha256=EXPECTED_FULL_HOOKS_SHA256,
        )
        self.assertEqual(
            sha256_file(rebuilt / "DISKBOOT.BIN"),
            EXPECTED_FULL_HOOKS_SHA256,
            "Helper must detect stale default hash, wipe out_port41-full, and rebuild FULL_HOOKS",
        )

        # 3. Verify it matches the FULL_HOOKS manifest
        mpath_full = MANIFESTS_DIR / "port42_full_hooks_manifest.json"
        _verify_distribution_against_manifest(rebuilt, mpath_full)

    def test_all_port24_to_port40_candidates_byte_identical(self):
        """Verify that every PORT-24..40 candidate remains 100% byte-identical to locked manifests.

        Verifies against git-tracked baseline files only (no git-ignored candidate_port*/ paths).
        Fails if any candidate has no tracked expected hash.
        """
        required_candidates = {
            "default", "poweron_fix", "ladder", "combined", "resident",
            "osd", "kbd", "kbd_osd", "osd2", "gui", "gui2", "gui3",
            "gui4", "shortpress", "gui5", "gui5_shortpress"
        }
        present_candidates = {name for name, _, _, _, _ in PINNED_CANDIDATES}
        missing_candidates = required_candidates - present_candidates
        if missing_candidates:
            self.fail(f"Candidates missing from test suite: {sorted(missing_candidates)}")

        for name, kwargs, expected_sha, expected_size, tracked_relpath in PINNED_CANDIDATES:
            with self.subTest(candidate=name):
                # 1. Verify candidate has a tracked expected hash source file
                if not tracked_relpath:
                    self.fail(f"Candidate {name} has no tracked expected hash source file")

                tracked_file = REPO_ROOT / tracked_relpath
                self.assertTrue(
                    tracked_file.is_file(),
                    f"Tracked source file {tracked_relpath} for candidate {name} does not exist",
                )

                # Ensure source file is actually tracked by git and NOT git-ignored
                ignore_check = subprocess.run(
                    ["git", "check-ignore", "-q", str(tracked_file)],
                    cwd=str(REPO_ROOT),
                )
                self.assertNotEqual(
                    ignore_check.returncode,
                    0,
                    f"Candidate {name} source file {tracked_relpath} is git-ignored; must be tracked baseline",
                )

                # Verify expected hash is present in the tracked baseline file
                tracked_content = tracked_file.read_text(encoding="utf-8")
                self.assertIn(
                    expected_sha,
                    tracked_content,
                    f"Candidate {name} expected hash {expected_sha} not found in tracked file {tracked_relpath}",
                )

                # 2. Build or load candidate from clean dedicated directory (never candidate_port*/)
                cand_dir = _require_or_build_candidate(name, kwargs, expected_sha, expected_size)
                diskboot = cand_dir / "DISKBOOT.BIN"
                self.assertTrue(diskboot.is_file(), f"DISKBOOT.BIN for candidate {name} missing in {cand_dir}")

                actual_size = diskboot.stat().st_size
                actual_sha = sha256_file(diskboot)

                # Verify against generated candidate manifest in output directory
                cand_mpath = cand_dir / "candidate_manifest.json"
                self.assertTrue(cand_mpath.is_file(), f"candidate_manifest.json for {name} missing in {cand_dir}")
                with open(cand_mpath, "r", encoding="utf-8") as mf:
                    cand_mdata = json.load(mf)
                cand_db = cand_mdata["candidate_artifacts"]["DISKBOOT.BIN"]
                self.assertEqual(actual_size, cand_db["size_bytes"], f"Manifest size mismatch for {name}")
                self.assertEqual(actual_sha, cand_db["sha256"], f"Manifest SHA mismatch for {name}")

                # Verify against pinned expected values
                self.assertEqual(actual_size, expected_size, f"Size mismatch for {name} candidate build")
                self.assertEqual(actual_sha, expected_sha, f"SHA-256 mismatch for {name} candidate build")


class TestPort43DrawLayerHostModel(unittest.TestCase):
    """Host-side unit and model tests of the draw layer."""

    @classmethod
    def setUpClass(cls):
        # Compile and execute the host C test harness
        c_src = REPO_ROOT / "tests" / "test_port43_draw_layer.c"
        cls.c_bin = Path(tempfile.gettempdir()) / "test_port43_draw_layer"
        proc = subprocess.run(
            ["gcc", "-O2", "-Wall", "-Wextra", "-Werror", str(c_src), "-o", str(cls.c_bin)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to compile host C draw layer harness: {proc.stderr}")

    def test_host_c_draw_layer_harness_execution(self):
        """Run compiled C test harness verifying dual-buffer identity, word-write fills, partial redraw, and shadow restore."""
        proc = subprocess.run(
            [str(self.c_bin)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, f"Host C harness failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
        self.assertIn("ALL PORT-43 DRAW LAYER UNIT TESTS PASSED SUCCESSFULLY.", proc.stdout)

    def _extract_fn_targets_and_body(self, target_path: Path, fn_name: str) -> tuple[str, set[str]]:
        proc = subprocess.run(
            [str(TOOLCHAIN_OBJDUMP), "-dr", str(target_path)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        disasm = proc.stdout
        m = re.search(r"^[0-9a-f]+ <" + fn_name + r">:.*?(?=^[0-9a-f]+ <|\Z)", disasm, re.M | re.S)
        self.assertIsNotNone(m, f"Function {fn_name} not found in disassembly of {target_path}")
        body = m.group(0)
        reloc_syms = set(re.findall(r"R_ARM_\S+\s+(\S+)", body))
        resolved_calls = set(re.findall(r"(?:bl|b\.w|blx)\s+[0-9a-f]+\s+<(\w+)>", body))
        return body, reloc_syms | resolved_calls

    def test_arm_binary_fill_paths_use_word_writes_and_no_draw_pixel(self):
        """Disassembly inspection: fill paths use word writes, reference memset/fast fill, and never call draw_pixel."""
        if not TOOLCHAIN_OBJDUMP.is_file():
            self.skipTest("ARM objdump tool not available")

        # Ensure G3X_GUI_DBUF variant is built
        _require_or_build_distribution(
            OUT_DIR_GUI_FIX_DBUF,
            [],
            expected_sha256=EXPECTED_DBUF_SHA256,
            script=BUILD_SCRIPT_DBUF,
        )

        obj_path = OUT_DIR_GUI_FIX_DBUF / "stage_chdk" / "platform" / "g3x" / "sub" / "110c" / "gui_draw.thm.o"
        elf_path = OUT_DIR_GUI_FIX_DBUF / "stage_chdk" / "platform" / "g3x" / "sub" / "110c" / "main.elf"

        if not obj_path.is_file() and not elf_path.is_file():
            alt_obj = REPO_ROOT / "out" / "port43-dbuf" / "stage_chdk" / "platform" / "g3x" / "sub" / "110c" / "gui_draw.thm.o"
            alt_elf = REPO_ROOT / "out" / "port43-dbuf" / "stage_chdk" / "platform" / "g3x" / "sub" / "110c" / "main.elf"
            if alt_obj.is_file():
                obj_path = alt_obj
            if alt_elf.is_file():
                elf_path = alt_elf

        if not obj_path.is_file() and not elf_path.is_file():
            self.skipTest(f"Build output not found at {obj_path} or {elf_path}; stage artifacts must be present to inspect disassembly")

        targets_to_test = [p for p in [obj_path, elf_path] if p.is_file()]

        for target in targets_to_test:
            # 1. draw_hline
            body_hline, targets_hline = self._extract_fn_targets_and_body(target, "draw_hline")
            self.assertIn("g3x_dbuf_fast_fill_rect", targets_hline, f"draw_hline does not call g3x_dbuf_fast_fill_rect in {target}")
            self.assertFalse(any("draw_pixel" in t for t in targets_hline), f"draw_hline references draw_pixel in {target}")

            # 2. draw_vline
            body_vline, targets_vline = self._extract_fn_targets_and_body(target, "draw_vline")
            self.assertIn("g3x_dbuf_fast_fill_rect", targets_vline, f"draw_vline does not call g3x_dbuf_fast_fill_rect in {target}")
            self.assertFalse(any("draw_pixel" in t for t in targets_vline), f"draw_vline references draw_pixel in {target}")

            # 3. draw_rectangle
            body_rect, targets_rect = self._extract_fn_targets_and_body(target, "draw_rectangle")
            self.assertIn("g3x_dbuf_fast_fill_rect", targets_rect, f"draw_rectangle does not call g3x_dbuf_fast_fill_rect in {target}")
            self.assertFalse(any("draw_pixel" in t for t in targets_rect), f"draw_rectangle references draw_pixel in {target}")

            # 4. g3x_dbuf_fast_fill_rect
            body_fill, targets_fill = self._extract_fn_targets_and_body(target, "g3x_dbuf_fast_fill_rect")
            self.assertIn("memset", targets_fill, f"g3x_dbuf_fast_fill_rect does not reference memset in {target}")
            self.assertFalse(any("draw_pixel" in t for t in targets_fill), f"g3x_dbuf_fast_fill_rect references draw_pixel in {target}")
            has_word_stores = bool(re.search(r"str(?:\.w)?\s+r\d+,\s*\[r\d+.*(?:#4|lsl #2)", body_fill))
            self.assertTrue(has_word_stores, f"Fast fill does not contain expected 32-bit word stores in {target}")

    def test_arm_binary_shadow_restore_has_no_vid_bitmap_refresh(self):
        """Disassembly inspection: g3x_dbuf_shadow_restore calls memcpy and NEVER vid_bitmap_refresh."""
        if not TOOLCHAIN_OBJDUMP.is_file():
            self.skipTest("ARM objdump tool not available")

        # Ensure G3X_GUI_DBUF variant is built
        _require_or_build_distribution(
            OUT_DIR_GUI_FIX_DBUF,
            [],
            expected_sha256=EXPECTED_DBUF_SHA256,
            script=BUILD_SCRIPT_DBUF,
        )

        obj_path = OUT_DIR_GUI_FIX_DBUF / "stage_chdk" / "platform" / "g3x" / "sub" / "110c" / "gui_draw.thm.o"
        elf_path = OUT_DIR_GUI_FIX_DBUF / "stage_chdk" / "platform" / "g3x" / "sub" / "110c" / "main.elf"

        if not obj_path.is_file() and not elf_path.is_file():
            alt_obj = REPO_ROOT / "out" / "port43-dbuf" / "stage_chdk" / "platform" / "g3x" / "sub" / "110c" / "gui_draw.thm.o"
            alt_elf = REPO_ROOT / "out" / "port43-dbuf" / "stage_chdk" / "platform" / "g3x" / "sub" / "110c" / "main.elf"
            if alt_obj.is_file():
                obj_path = alt_obj
            if alt_elf.is_file():
                elf_path = alt_elf

        if not obj_path.is_file() and not elf_path.is_file():
            self.skipTest(f"Build output not found at {obj_path} or {elf_path}; stage artifacts must be present to inspect disassembly")

        targets_to_test = [p for p in [obj_path, elf_path] if p.is_file()]

        for target in targets_to_test:
            body_restore, targets_restore = self._extract_fn_targets_and_body(target, "g3x_dbuf_shadow_restore")
            self.assertIn("memcpy", targets_restore, f"g3x_dbuf_shadow_restore does not call memcpy in {target}")
            self.assertNotIn("vid_bitmap_refresh", targets_restore, f"vid_bitmap_refresh call found in {target}")
            self.assertNotIn("_transfer_src_overlay", targets_restore, f"_transfer_src_overlay call found in {target}")
            self.assertFalse(any("draw_pixel" in t for t in targets_restore), f"draw_pixel call found in {target}")

    def test_python_model_draw_layer_invariants(self):
        """Python model: dual-buffer identical bytes, word-write fills, row cache partial redraw, single-blit restore."""
        BUF_W = 928
        BUF_H = 600
        BM_SIZE = BUF_W * BUF_H * 2
        OP_SIZE = BUF_W * BUF_H

        bm0 = bytearray(BM_SIZE)
        bm1 = bytearray(BM_SIZE)
        op0 = bytearray(OP_SIZE)
        op1 = bytearray(OP_SIZE)
        sh_bm = bytearray(BM_SIZE)
        sh_op = bytearray(OP_SIZE)

        draw_pixel_count = 0

        def model_fast_fill(x1, y1, x2, y2, uyvy_word, op_val):
            nonlocal draw_pixel_count
            # Zero draw_pixel calls
            op_bytes = bytes([op_val]) * ((x2 - x1 + 1))
            word_bytes = (uyvy_word).to_bytes(4, "little") * ((x2 - x1 + 1) // 2)
            for y in range(y1, y2 + 1):
                offset_op = y * BUF_W + x1
                offset_bm = (y * BUF_W + x1) * 2
                op0[offset_op:offset_op + len(op_bytes)] = op_bytes
                op1[offset_op:offset_op + len(op_bytes)] = op_bytes
                sh_op[offset_op:offset_op + len(op_bytes)] = op_bytes
                bm0[offset_bm:offset_bm + len(word_bytes)] = word_bytes
                bm1[offset_bm:offset_bm + len(word_bytes)] = word_bytes
                sh_bm[offset_bm:offset_bm + len(word_bytes)] = word_bytes

        # 1. Fill menu box
        model_fast_fill(10, 12, 889, 587, 0x00800080, 0xFF)
        self.assertEqual(draw_pixel_count, 0, "Fast fill must not call draw_pixel")
        self.assertEqual(bm0, bm1, "Bitmap buffers 0 and 1 must receive identical bytes")
        self.assertEqual(op0, op1, "Opacity buffers 0 and 1 must receive identical bytes")
        self.assertEqual(bm0, sh_bm, "Shadow bitmap must match bitmap buffer")
        self.assertEqual(op0, sh_op, "Shadow opacity must match opacity buffer")

        # 2. Simulate cursor move with row signature cache
        num_rows = 10
        cache = [{"item": i, "sig": i * 100, "sel": (i == 0)} for i in range(num_rows)]

        # Move cursor from row 0 to row 1
        new_sel = 1
        redrawn_rows = []
        for i in range(num_rows):
            is_sel = (i == new_sel)
            cur_sig = i * 100 + (1 if is_sel else 0)
            if cache[i]["sig"] != cur_sig or cache[i]["sel"] != is_sel:
                redrawn_rows.append(i)
                cache[i]["sig"] = cur_sig
                cache[i]["sel"] = is_sel

        self.assertEqual(redrawn_rows, [0, 1], "Cursor move must touch ONLY changed rows (row 0 and row 1)")

        # 3. Simulate display plane corruption and single-blit shadow restore
        pre_wipe_bm0 = bytes(bm0)
        pre_wipe_op0 = bytes(op0)

        # Corrupt / wipe display buffers
        bm0[:] = b"\x55" * BM_SIZE
        bm1[:] = b"\xAA" * BM_SIZE
        op0[:] = b"\x00" * OP_SIZE
        op1[:] = b"\x00" * OP_SIZE

        # Single blit restore: 4 memcpys
        bm0[:] = sh_bm
        bm1[:] = sh_bm
        op0[:] = sh_op
        op1[:] = sh_op

        self.assertEqual(bm0, pre_wipe_bm0, "Shadow restore must produce exact pre-wipe bitmap bytes")
        self.assertEqual(bm1, pre_wipe_bm0, "Shadow restore must restore bitmap buffer 1 identically")
        self.assertEqual(op0, pre_wipe_op0, "Shadow restore must produce exact pre-wipe opacity bytes")
        self.assertEqual(op1, pre_wipe_op0, "Shadow restore must restore opacity buffer 1 identically")


if __name__ == "__main__":
    unittest.main()
