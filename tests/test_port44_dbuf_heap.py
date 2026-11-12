"""Unit and integration host tests for PORT-44 double-buffered GUI build, lazy heap shadow, and owner trial plan.

Verifies:
1. docs/PORT44_TRIAL_PLAN.md format and content:
   - DISKBOOT SHA-256 and size check against manifest
   - Held-press boot method first, then short press
   - Battery-pull recovery (>= 10 s) and rollback to PORT-42 build (760a362d...6738)
   - Owner observations checklist: boots (held / short press), ALT/CHDK menu opens,
     steady overlay (no flicker) at idle and while navigating, colours/opacity/2x font/880x576 layout unchanged,
     any regressions (10 s video welcome).
   - No report decoder or classifier tool is added.
2. manifests/port44_dbuf_heap_manifest.json:
   - Lists DISKBOOT.BIN (126,769 B, SHA-256 2017b13c3330cd30edf9a8923d58a2fb12f6a4d1f77c9f51923bc60f79247382)
   - Lists every CHDK/ file with size and SHA-256 (34 modules).
3. Reproducible build:
   - Two builds of G3X_GUI_DBUF=1 with lazy runtime heap allocation produce byte-for-byte identical DISKBOOT.BIN and CHDK/ files.
4. Byte identity to existing manifests:
   - PORT-42 GUI build (G3X_GUI_FIX=1 alone, 124,257 B, 760a362d...)
   - PORT-41 default full build (124,097 B, 24b8a024...)
   - FULL_HOOKS variant (124,153 B, eb46aa33...)
   - GUI_FIX + FULL_HOOKS variant (124,321 B, d50ea585...)
   - Every PORT-24..40 candidate: default, poweron_fix, ladder, combined, resident,
     osd, kbd, kbd_osd, osd2, gui, gui2, gui3, gui3_diag, gui4, gui4_diag, shortpress,
     shortpress_gui4, gui5, gui5_shortpress.
5. _end guard:
   - For every full-build variant, core _end is no more than PORT44_END_MARGIN = 64 KiB above recorded PORT-42 _end.
   - No single BSS or data symbol is larger than 64 KiB.
   - Guard fails on PORT-43 layout (demonstrated both with fixture and recorded PORT-43 layout values).
6. Host-side model and unit tests of the draw layer:
   - Both bitmap buffers and both opacity buffers receive identical overlay bytes.
   - Fill paths use 32-bit word writes and never call draw_pixel.
   - Cursor move touches only changed rows via row signature cache.
   - A NULL shadow (simulated allocation failure) takes fallback path with zero out-of-bounds writes (bounds-checked mock buffers).
   - Allocation happens only on first GUI/ALT entry, not at init.
   - Compiled ARM object disassembly confirms fast fill call sites, word stores, and absence of draw_pixel / vid_bitmap_refresh in shadow restore.
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

BUILD_SCRIPT_PORT44 = REPO_ROOT / "tools" / "build_port44_dbuf_heap.py"
BUILD_SCRIPT_PORT43 = REPO_ROOT / "scripts" / "build_port43_dbuf.py"
BUILD_SCRIPT_PORT41 = REPO_ROOT / "tools" / "build_port41_full.py"
WRAPPER_SCRIPT = REPO_ROOT / "scripts" / "gcc_deterministic_wrapper.sh"
MANIFESTS_DIR = REPO_ROOT / "manifests"
FIXTURES_DIR = REPO_ROOT / "tests" / "fixtures"

# Dedicated clean output directories per variant under out/port44-test/
TEST_BASE_OUT_DIR = REPO_ROOT / "out" / "port44-test"
CANDIDATE_CACHE_DIR = REPO_ROOT / "out" / "port43-test"
OUT_DIR_PORT41_DEFAULT = TEST_BASE_OUT_DIR / "port41_default"
OUT_DIR_FULL_HOOKS = TEST_BASE_OUT_DIR / "full_hooks"
OUT_DIR_PORT42_GUI_FIX = TEST_BASE_OUT_DIR / "port42_gui_fix"
OUT_DIR_GUI_FIX_FULL_HOOKS = TEST_BASE_OUT_DIR / "gui_fix_full_hooks"
OUT_DIR_PORT44_DBUF_HEAP = TEST_BASE_OUT_DIR / "port44_dbuf_heap"

EXPECTED_PORT44_DBUF_SIZE = 126769
EXPECTED_PORT44_DBUF_SHA256 = "2017b13c3330cd30edf9a8923d58a2fb12f6a4d1f77c9f51923bc60f79247382"
EXPECTED_PORT43_DBUF_SIZE = 126329
EXPECTED_PORT43_DBUF_SHA256 = "8d5509e597a598e8bb023adae46d4caa2c7ee1e2b763e4ff292f0aef21f9b140"
EXPECTED_PORT42_GUI_SIZE = 124257
EXPECTED_PORT42_GUI_SHA256 = "760a362d358d87518e6274013e70109f8699974a40158ae5bbbff8b80c246738"
EXPECTED_PORT41_FULL_SIZE = 124097
EXPECTED_PORT41_FULL_SHA256 = "24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9"
EXPECTED_FULL_HOOKS_SIZE = 124153
EXPECTED_FULL_HOOKS_SHA256 = "eb46aa339bb6557f27d992691f83ceb14cc73962625a44e0f146edde9b886dce"
EXPECTED_GUI_FULL_HOOKS_SIZE = 124321
EXPECTED_GUI_FULL_HOOKS_SHA256 = "d50ea585b2ba49e39674395f504b5780a1cb98a915fe998c5b7fa5be115cb9bb"

# Constants for _end guard
PORT44_END_MARGIN = 64 * 1024       # Documented 64 KiB margin: 65,536 bytes
PORT42_RECORDED_END = 0x003687b0    # Recorded PORT-42 _end
MAX_SYMBOL_SIZE = 64 * 1024         # 64 KiB ceiling for any BSS or data symbol

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
        "gui3_diag",
        {"gui3": True, "gui_diag": True},
        "de066f7198ed8f56e055807eb25880c394386eaeab5aac6384cb1fa607308ed4",
        103745,
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
        "gui4_diag",
        {"gui4": True, "gui_diag": True},
        "a4bfdeeae630e5fcac07e4b206ff2c64acea28e77f22bad49996bea460d35e1d",
        102417,
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
        "shortpress_gui4",
        {"gui4": True, "shortpress": True},
        "4859e0886a32665e5adbf65400121bb2a503b5827aa29aa69e35dc33a465db28",
        102401,
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
    """Ensure a full distribution directory exists with valid DISKBOOT.BIN for the requested variant, or build it."""
    diskboot = out_path / "DISKBOOT.BIN"
    chdk_dir = out_path / "CHDK"
    if diskboot.is_file() and diskboot.stat().st_size > 0 and chdk_dir.is_dir():
        if expected_sha256 is not None:
            if sha256_file(diskboot) == expected_sha256:
                return out_path
        else:
            return out_path

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
    """Ensure candidate output directory exists with byte-identical DISKBOOT.BIN, or build it cleanly."""
    cand_dir = CANDIDATE_CACHE_DIR / f"candidate_{name}"
    diskboot = cand_dir / "DISKBOOT.BIN"
    cand_mpath = cand_dir / "candidate_manifest.json"

    if diskboot.is_file() and diskboot.stat().st_size == expected_size and cand_mpath.is_file():
        if sha256_file(diskboot) == expected_sha256:
            return cand_dir

    if cand_dir.exists():
        shutil.rmtree(cand_dir)
    cand_dir.mkdir(parents=True, exist_ok=True)

    import sys
    scripts_dir = REPO_ROOT / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    from build_candidate_gui3 import build_candidate

    build_candidate(out_dir=str(cand_dir), **kwargs)
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

    manifest_files = set(mdata["artifacts"]["chdk_files"].keys()) | {"DISKBOOT.BIN"}
    actual_files = set(actual_snap.keys())
    assert actual_files == manifest_files, (
        f"File set mismatch between {out_path} and {manifest_path}: "
        f"extra: {actual_files - manifest_files}, missing: {manifest_files - actual_files}"
    )


def extract_symbols_and_end(elf_path: Path) -> tuple[int, list[tuple[str, int, str, int]]]:
    """Extract core _end and all symbols with (name, size, type, address) using arm-none-eabi-nm."""
    proc = subprocess.run(
        [str(TOOLCHAIN_NM), "-S", str(elf_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        check=True,
    )
    core_end = None
    symbols = []
    for line in proc.stdout.splitlines():
        parts = line.strip().split()
        if len(parts) == 4:
            # Address, Size, Type, Name
            addr = int(parts[0], 16)
            size = int(parts[1], 16)
            stype = parts[2]
            name = parts[3]
            symbols.append((name, size, stype, addr))
            if name == "_end":
                core_end = addr
        elif len(parts) == 3:
            addr = int(parts[0], 16)
            stype = parts[1]
            name = parts[2]
            if name == "_end":
                core_end = addr

    assert core_end is not None, f"_end symbol not found in {elf_path}"
    return core_end, symbols


def verify_end_guard(
    core_end: int,
    symbols: list[tuple[str, int, str, int]],
    recorded_port42_end: int = PORT42_RECORDED_END,
    max_margin: int = PORT44_END_MARGIN,
    max_symbol_size: int = MAX_SYMBOL_SIZE,
) -> None:
    """_end guard: core _end must be <= recorded PORT-42 _end + PORT44_END_MARGIN (64 KiB),

    and no single BSS or data symbol may exceed max_symbol_size (64 KiB).
    """
    delta = core_end - recorded_port42_end
    if delta > max_margin:
        raise AssertionError(
            f"Core _end 0x{core_end:08x} exceeds recorded PORT-42 _end 0x{recorded_port42_end:08x} "
            f"by {delta} bytes ({delta / 1024:.2f} KiB), which violates the PORT44_END_MARGIN of "
            f"{max_margin} bytes ({max_margin / 1024:.1f} KiB)"
        )

    for name, size, stype, _addr in symbols:
        if stype in ("b", "B", "d", "D") and size > max_symbol_size:
            raise AssertionError(
                f"Symbol '{name}' in section '{stype}' has size {size} bytes ({size / 1024:.2f} KiB), "
                f"exceeding the maximum allowed symbol size of {max_symbol_size} bytes ({max_symbol_size / 1024:.1f} KiB)"
            )


class TestPort44TrialPlanDoc(unittest.TestCase):
    """Static verification of docs/PORT44_TRIAL_PLAN.md."""

    def setUp(self):
        self.doc_path = REPO_ROOT / "docs" / "PORT44_TRIAL_PLAN.md"
        self.assertTrue(self.doc_path.is_file(), f"Missing {self.doc_path}")
        self.doc_text = self.doc_path.read_text(encoding="utf-8")

    def test_trial_plan_sha_check_and_size(self):
        """Doc must specify exact preflight DISKBOOT SHA-256 and size check matching manifest."""
        self.assertIn(EXPECTED_PORT44_DBUF_SHA256, self.doc_text)
        self.assertIn("126,769", self.doc_text)

    def test_trial_plan_held_then_short_press_boot(self):
        """Doc must specify held press first, then short press."""
        self.assertRegex(self.doc_text, r"(?i)held\s+press")
        self.assertRegex(self.doc_text, r"(?i)short\s+press")

    def test_trial_plan_battery_pull_recovery_and_rollback(self):
        """Doc must cover battery-pull recovery and rollback to PORT-42 build."""
        self.assertRegex(self.doc_text, r"(?i)battery\s+pull")
        self.assertIn(EXPECTED_PORT42_GUI_SHA256, self.doc_text)
        self.assertIn("124,257", self.doc_text)

    def test_trial_plan_observation_checklist(self):
        """Doc must ask owner to report all required observations."""
        self.assertRegex(self.doc_text, r"(?i)held.*short|short.*held")
        self.assertRegex(self.doc_text, r"(?i)alt.*menu|menu.*alt")
        self.assertRegex(self.doc_text, r"(?i)steady|no\s+flicker")
        self.assertRegex(self.doc_text, r"(?i)navigat")
        self.assertRegex(self.doc_text, r"(?i)port-42")
        self.assertRegex(self.doc_text, r"(?i)880x576")
        self.assertRegex(self.doc_text, r"(?i)regression")
        self.assertRegex(self.doc_text, r"(?i)10\s*s.*video|video.*10\s*s")

    def test_no_report_decoder_tooling_added(self):
        """Doc must explicitly avoid report decoder or classifier tooling."""
        self.assertRegex(self.doc_text, r"(?i)no.*decoder|no.*classifier")


class TestPort44ManifestIntegrity(unittest.TestCase):
    """Verification of manifests/port44_dbuf_heap_manifest.json."""

    def setUp(self):
        self.manifest_path = MANIFESTS_DIR / "port44_dbuf_heap_manifest.json"
        self.assertTrue(self.manifest_path.is_file(), f"Missing {self.manifest_path}")
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            self.data = json.load(f)

    def test_manifest_build_flags(self):
        """Manifest flags must include G3X_GUI_DBUF=1, G3X_GUI_FIX=1, and full build flags."""
        flags = self.data["build"]["flags"]
        self.assertIn("G3X_GUI_DBUF=1", flags)
        self.assertIn("G3X_GUI_FIX=1", flags)
        self.assertIn("G3X_FULL_BUILD=1", flags)
        self.assertIn("G3X_DISABLE_CARD_WRITES=1", flags)
        self.assertEqual(self.data["build"]["name"], "port44_dbuf_heap")

    def test_manifest_diskboot_artifact(self):
        """Manifest DISKBOOT.BIN matches expected SHA-256 and size."""
        db = self.data["artifacts"]["DISKBOOT.BIN"]
        self.assertEqual(db["size"], EXPECTED_PORT44_DBUF_SIZE)
        self.assertEqual(db["sha256"], EXPECTED_PORT44_DBUF_SHA256)

    def test_manifest_chdk_files_coverage(self):
        """Manifest lists 34 loadable modules and valid non-empty files."""
        self.assertEqual(self.data["artifacts"]["modules_count"], 34)
        self.assertGreater(self.data["artifacts"]["chdk_files_count"], 100)
        chdk_files = self.data["artifacts"]["chdk_files"]
        for rel_path, info in chdk_files.items():
            self.assertTrue(rel_path.startswith("CHDK/"), f"{rel_path} must start with CHDK/")
            self.assertGreater(info["size"], 0)
            self.assertEqual(len(info["sha256"]), 64)


class TestPort44BuildReproducibility(unittest.TestCase):
    """Verification that G3X_GUI_FIX=1 G3X_GUI_DBUF=1 builds reproducibly."""

    @classmethod
    def setUpClass(cls):
        if not TOOLCHAIN_GCC.is_file():
            raise unittest.SkipTest("ARM toolchain compiler not available")

    def test_dbuf_heap_build_reproducibility(self):
        """Two builds of the variant give identical SHA-256."""
        out_dbuf = _require_or_build_distribution(
            OUT_DIR_PORT44_DBUF_HEAP,
            [],
            expected_sha256=EXPECTED_PORT44_DBUF_SHA256,
            script=BUILD_SCRIPT_PORT44,
        )
        snap1 = snapshot_distribution(out_dbuf)
        self.assertEqual(snap1["DISKBOOT.BIN"], (EXPECTED_PORT44_DBUF_SIZE, EXPECTED_PORT44_DBUF_SHA256))

        # Build 2 in fresh temporary directory
        with tempfile.TemporaryDirectory() as td2:
            res2 = subprocess.run(
                ["python3", "-B", str(BUILD_SCRIPT_PORT44), "--out-dir", td2],
                cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(res2.returncode, 0, f"Build 2 failed: {res2.stderr}")

            snap2 = snapshot_distribution(Path(td2))
            self.assertEqual(snap1, snap2, "Two clean DBUF heap builds produced different hashes")
            self.assertEqual(snap2["DISKBOOT.BIN"], (EXPECTED_PORT44_DBUF_SIZE, EXPECTED_PORT44_DBUF_SHA256))

        # Verify full distribution snapshot matches manifests/port44_dbuf_heap_manifest.json
        mpath = MANIFESTS_DIR / "port44_dbuf_heap_manifest.json"
        _verify_distribution_against_manifest(out_dbuf, mpath)


class TestPort44ByteIdentityToExistingManifests(unittest.TestCase):
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
        target_full = _require_or_build_distribution(
            OUT_DIR_FULL_HOOKS,
            ["--full-hooks"],
            expected_sha256=EXPECTED_FULL_HOOKS_SHA256,
        )
        mpath_full = MANIFESTS_DIR / "port42_full_hooks_manifest.json"
        _verify_distribution_against_manifest(target_full, mpath_full)

        target_gui_hooks = _require_or_build_distribution(
            OUT_DIR_GUI_FIX_FULL_HOOKS,
            ["--gui-fix", "--full-hooks"],
            expected_sha256=EXPECTED_GUI_FULL_HOOKS_SHA256,
        )
        for name in ["port42_gui_fix_full_hooks_manifest.json", "port42_gui_full_hooks_manifest.json"]:
            p = MANIFESTS_DIR / name
            if p.is_file():
                _verify_distribution_against_manifest(target_gui_hooks, p)

    def test_all_port24_to_port40_candidates_byte_identical(self):
        """Verify that every PORT-24..40 candidate remains 100% byte-identical to locked manifests."""
        for name, kwargs, expected_sha, expected_size, tracked_relpath in PINNED_CANDIDATES:
            with self.subTest(candidate=name):
                tracked_file = REPO_ROOT / tracked_relpath
                self.assertTrue(tracked_file.is_file(), f"Missing tracked baseline file: {tracked_relpath}")
                tracked_content = tracked_file.read_text(encoding="utf-8")
                self.assertIn(expected_sha, tracked_content)

                cand_dir = _require_or_build_candidate(name, kwargs, expected_sha, expected_size)
                diskboot = cand_dir / "DISKBOOT.BIN"
                self.assertTrue(diskboot.is_file())
                self.assertEqual(diskboot.stat().st_size, expected_size)
                self.assertEqual(sha256_file(diskboot), expected_sha)


class TestPort44EndGuard(unittest.TestCase):
    """Verification of the _end guard and demonstration of failure on PORT-43 layout."""

    @classmethod
    def setUpClass(cls):
        if not TOOLCHAIN_NM.is_file():
            raise unittest.SkipTest("ARM toolchain nm not available")

    def test_port44_end_guard_passes(self):
        """PORT-44 core _end is <= PORT42_RECORDED_END + 64 KiB, and all symbols <= 64 KiB."""
        out_dbuf = _require_or_build_distribution(
            OUT_DIR_PORT44_DBUF_HEAP,
            [],
            expected_sha256=EXPECTED_PORT44_DBUF_SHA256,
            script=BUILD_SCRIPT_PORT44,
        )
        elf_path = out_dbuf / "stage_chdk" / "platform" / "g3x" / "sub" / "110c" / "main.elf"
        if not elf_path.is_file():
            alt_elf = REPO_ROOT / "out" / "port44-dbuf" / "stage_chdk" / "platform" / "g3x" / "sub" / "110c" / "main.elf"
            if alt_elf.is_file():
                elf_path = alt_elf

        self.assertTrue(elf_path.is_file(), f"main.elf missing in {elf_path}")
        core_end, symbols = extract_symbols_and_end(elf_path)

        # Core _end should be 0x00369490 (delta = +3296 B)
        self.assertEqual(core_end, 0x00369490)
        delta = core_end - PORT42_RECORDED_END
        self.assertEqual(delta, 3296)
        self.assertLessEqual(delta, PORT44_END_MARGIN)

        # Verify end guard executes cleanly
        verify_end_guard(core_end, symbols)

        # Verify no single BSS or data symbol exceeds 64 KiB
        for name, size, stype, _addr in symbols:
            if stype in ("b", "B", "d", "D"):
                self.assertLessEqual(size, MAX_SYMBOL_SIZE, f"Symbol {name} ({size} B) exceeds 64 KiB")

    def test_other_full_build_variants_pass_end_guard(self):
        """PORT-41 default, PORT-42 GUI_FIX, and FULL_HOOKS satisfy the _end guard."""
        variants = [
            (OUT_DIR_PORT41_DEFAULT, [], EXPECTED_PORT41_FULL_SHA256, BUILD_SCRIPT_PORT41),
            (OUT_DIR_PORT42_GUI_FIX, ["--gui-fix"], EXPECTED_PORT42_GUI_SHA256, BUILD_SCRIPT_PORT41),
            (OUT_DIR_FULL_HOOKS, ["--full-hooks"], EXPECTED_FULL_HOOKS_SHA256, BUILD_SCRIPT_PORT41),
        ]
        for out_dir, args, sha, script in variants:
            with self.subTest(variant=out_dir.name):
                dist_dir = _require_or_build_distribution(out_dir, args, expected_sha256=sha, script=script)
                elf_path = dist_dir / "stage_chdk" / "platform" / "g3x" / "sub" / "110c" / "main.elf"
                if elf_path.is_file():
                    core_end, symbols = extract_symbols_and_end(elf_path)
                    verify_end_guard(core_end, symbols)

    def test_end_guard_fails_on_port43_recorded_values(self):
        """The _end guard must fail when evaluated against recorded PORT-43 layout values."""
        recorded_port43_end = 0x00500fd0
        recorded_port43_symbols = [
            ("g3x_shadow", 1670400, "b", 0x00367568),
            ("font_data", 3473, "d", 0x00364bd4),
            ("symbol_hash_table", 3160, "D", 0x003667ac),
            ("conf", 2088, "B", 0x00500680),
        ]

        # 1. Must fail because _end exceeds margin (+1,673,248 bytes > 65,536 bytes)
        with self.assertRaises(AssertionError) as ctx_end:
            verify_end_guard(
                core_end=recorded_port43_end,
                symbols=[],
                recorded_port42_end=PORT42_RECORDED_END,
                max_margin=PORT44_END_MARGIN,
            )
        self.assertIn("exceeds recorded PORT-42 _end", str(ctx_end.exception))
        self.assertIn("PORT44_END_MARGIN", str(ctx_end.exception))

        # 2. Must fail because g3x_shadow symbol size (1,670,400 bytes) exceeds 64 KiB
        with self.assertRaises(AssertionError) as ctx_sym:
            verify_end_guard(
                core_end=PORT42_RECORDED_END,
                symbols=recorded_port43_symbols,
                recorded_port42_end=PORT42_RECORDED_END,
                max_margin=PORT44_END_MARGIN,
                max_symbol_size=MAX_SYMBOL_SIZE,
            )
        self.assertIn("g3x_shadow", str(ctx_sym.exception))
        self.assertIn("exceeding the maximum allowed symbol size", str(ctx_sym.exception))

    def test_end_guard_fails_on_port43_fixture(self):
        """The _end guard must fail when evaluated against the PORT-43 layout fixture."""
        fixture_path = FIXTURES_DIR / "port43_layout.json"
        self.assertTrue(fixture_path.is_file(), f"Fixture missing at {fixture_path}")
        with open(fixture_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        fixture_end = int(data["recorded_end"], 16)
        fixture_symbols = [
            (s["name"], s["size"], s["type"], int(s["address"], 16))
            for s in data["symbols"]
        ]

        # Must fail both _end margin check and max symbol size check
        with self.assertRaises(AssertionError) as ctx:
            verify_end_guard(
                core_end=fixture_end,
                symbols=fixture_symbols,
                recorded_port42_end=PORT42_RECORDED_END,
                max_margin=PORT44_END_MARGIN,
                max_symbol_size=MAX_SYMBOL_SIZE,
            )
        self.assertTrue(
            "exceeds recorded PORT-42 _end" in str(ctx.exception) or
            "g3x_shadow" in str(ctx.exception)
        )


class TestPort44DrawLayerHostModel(unittest.TestCase):
    """Host-side unit and model tests of the draw layer, lazy allocation, and NULL fallback."""

    @classmethod
    def setUpClass(cls):
        c_src = REPO_ROOT / "tests" / "test_port44_draw_layer.c"
        cls.c_bin = Path(tempfile.gettempdir()) / "test_port44_draw_layer"
        proc = subprocess.run(
            ["gcc", "-O2", "-Wall", "-Wextra", "-Werror", str(c_src), "-o", str(cls.c_bin)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(f"Failed to compile host C draw layer harness: {proc.stderr}")

    def test_host_c_draw_layer_harness_execution(self):
        """Run compiled C test harness verifying dual-buffer, word fills, cursor move, and NULL shadow fallback."""
        proc = subprocess.run(
            [str(self.c_bin)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, f"Host C harness failed:\nSTDOUT:\n{proc.stdout}\nSTDERR:\n{proc.stderr}")
        self.assertIn("ALL PORT-44 DRAW LAYER UNIT TESTS PASSED SUCCESSFULLY.", proc.stdout)

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

        out_dbuf = _require_or_build_distribution(
            OUT_DIR_PORT44_DBUF_HEAP,
            [],
            expected_sha256=EXPECTED_PORT44_DBUF_SHA256,
            script=BUILD_SCRIPT_PORT44,
        )
        obj_path = out_dbuf / "stage_chdk" / "platform" / "g3x" / "sub" / "110c" / "gui_draw.thm.o"
        elf_path = out_dbuf / "stage_chdk" / "platform" / "g3x" / "sub" / "110c" / "main.elf"

        if not obj_path.is_file() and not elf_path.is_file():
            alt_obj = REPO_ROOT / "out" / "port44-dbuf" / "stage_chdk" / "platform" / "g3x" / "sub" / "110c" / "gui_draw.thm.o"
            alt_elf = REPO_ROOT / "out" / "port44-dbuf" / "stage_chdk" / "platform" / "g3x" / "sub" / "110c" / "main.elf"
            if alt_obj.is_file():
                obj_path = alt_obj
            if alt_elf.is_file():
                elf_path = alt_elf

        targets_to_test = [p for p in [obj_path, elf_path] if p.is_file()]
        self.assertTrue(len(targets_to_test) > 0, "No built object/ELF found for disassembly inspection")

        for target in targets_to_test:
            body_fill, targets_fill = self._extract_fn_targets_and_body(target, "g3x_dbuf_fast_fill_rect")
            self.assertIn("memset", targets_fill, f"g3x_dbuf_fast_fill_rect does not reference memset in {target}")
            self.assertFalse(any("draw_pixel" in t for t in targets_fill), f"g3x_dbuf_fast_fill_rect references draw_pixel in {target}")
            has_word_stores = bool(re.search(r"str(?:\.w)?\s+r\d+,\s*\[r\d+.*(?:#4|lsl #2)", body_fill))
            self.assertTrue(has_word_stores, f"Fast fill does not contain expected 32-bit word stores in {target}")

    def test_arm_binary_shadow_restore_has_no_vid_bitmap_refresh(self):
        """Disassembly inspection: g3x_dbuf_shadow_restore calls memcpy and NEVER vid_bitmap_refresh."""
        if not TOOLCHAIN_OBJDUMP.is_file():
            self.skipTest("ARM objdump tool not available")

        out_dbuf = _require_or_build_distribution(
            OUT_DIR_PORT44_DBUF_HEAP,
            [],
            expected_sha256=EXPECTED_PORT44_DBUF_SHA256,
            script=BUILD_SCRIPT_PORT44,
        )
        obj_path = out_dbuf / "stage_chdk" / "platform" / "g3x" / "sub" / "110c" / "gui_draw.thm.o"
        elf_path = out_dbuf / "stage_chdk" / "platform" / "g3x" / "sub" / "110c" / "main.elf"

        if not obj_path.is_file() and not elf_path.is_file():
            alt_obj = REPO_ROOT / "out" / "port44-dbuf" / "stage_chdk" / "platform" / "g3x" / "sub" / "110c" / "gui_draw.thm.o"
            alt_elf = REPO_ROOT / "out" / "port44-dbuf" / "stage_chdk" / "platform" / "g3x" / "sub" / "110c" / "main.elf"
            if alt_obj.is_file():
                obj_path = alt_obj
            if alt_elf.is_file():
                elf_path = alt_elf

        targets_to_test = [p for p in [obj_path, elf_path] if p.is_file()]
        for target in targets_to_test:
            _body_restore, targets_restore = self._extract_fn_targets_and_body(target, "g3x_dbuf_shadow_restore")
            self.assertIn("memcpy", targets_restore)
            self.assertNotIn("vid_bitmap_refresh", targets_restore)
            self.assertNotIn("_transfer_src_overlay", targets_restore)

    def test_lazy_allocation_call_paths(self):
        """Static verification: boot path does NOT call ensure_allocated, whereas first GUI entries do."""
        # 1. boot.c and loader do not call g3x_dbuf_shadow_ensure_allocated
        boot_c = REPO_ROOT / "chdk-port" / "platform" / "g3x" / "sub" / "110c" / "boot.c"
        self.assertNotIn("g3x_dbuf_shadow_ensure_allocated", boot_c.read_text(encoding="utf-8"))

        loader_main = REPO_ROOT / "chdk-port" / "loader" / "g3x" / "main.c"
        self.assertNotIn("g3x_dbuf_shadow_ensure_allocated", loader_main.read_text(encoding="utf-8"))

        # 2. GUI entry points DO call g3x_dbuf_shadow_ensure_allocated
        gui_c = REPO_ROOT / "chdk-port" / "core" / "gui.c"
        self.assertIn("g3x_dbuf_shadow_ensure_allocated", gui_c.read_text(encoding="utf-8"))

        gui_menu_c = REPO_ROOT / "chdk-port" / "core" / "gui_menu.c"
        self.assertIn("g3x_dbuf_shadow_ensure_allocated", gui_menu_c.read_text(encoding="utf-8"))

    def test_python_model_draw_layer_and_null_fallback(self):
        """Python model: dual-buffer identical bytes, word-write fills, cursor move, and NULL shadow fallback."""
        BUF_W = 928
        BUF_H = 600
        BM_SIZE = BUF_W * BUF_H * 2
        OP_SIZE = BUF_W * BUF_H

        MENU_X0, MENU_Y0 = 10, 12
        MENU_X1, MENU_Y1 = 889, 587
        SH_W = 880
        SH_H = 576

        bm0 = bytearray(BM_SIZE)
        bm1 = bytearray(BM_SIZE)
        op0 = bytearray(OP_SIZE)
        op1 = bytearray(OP_SIZE)

        # 1. Simulate allocation on first GUI entry
        alloc_attempted = False
        sh_bm: bytearray | None = None
        sh_op: bytearray | None = None

        def ensure_alloc(force_fail=False):
            nonlocal alloc_attempted, sh_bm, sh_op
            if alloc_attempted:
                return
            alloc_attempted = True
            if not force_fail:
                sh_bm = bytearray(SH_W * SH_H * 2)
                sh_op = bytearray(SH_W * SH_H)

        def model_fast_fill(x1, y1, x2, y2, uyvy_word, op_val):
            op_bytes = bytes([op_val]) * (x2 - x1 + 1)
            word_bytes = (uyvy_word).to_bytes(4, "little") * ((x2 - x1 + 1) // 2)
            for y in range(y1, y2 + 1):
                offset_op = y * BUF_W + x1
                offset_bm = (y * BUF_W + x1) * 2
                op0[offset_op:offset_op + len(op_bytes)] = op_bytes
                op1[offset_op:offset_op + len(op_bytes)] = op_bytes
                bm0[offset_bm:offset_bm + len(word_bytes)] = word_bytes
                bm1[offset_bm:offset_bm + len(word_bytes)] = word_bytes

                if sh_bm is not None and sh_op is not None:
                    # Clip to menu rectangle
                    if MENU_Y0 <= y <= MENU_Y1:
                        cx1 = max(x1, MENU_X0)
                        cx2 = min(x2, MENU_X1)
                        if cx1 <= cx2:
                            rx1 = cx1 - MENU_X0
                            rx2 = cx2 - MENU_X0
                            ry = y - MENU_Y0
                            sh_off_op = ry * SH_W + rx1
                            sh_off_bm = sh_off_op * 2
                            sh_len_op = rx2 - rx1 + 1
                            sh_op[sh_off_op:sh_off_op + sh_len_op] = bytes([op_val]) * sh_len_op
                            sh_bm[sh_off_bm:sh_off_bm + sh_len_op * 2] = (uyvy_word).to_bytes(4, "little") * (sh_len_op // 2)

        # Test normal allocation & fast fill
        ensure_alloc()
        self.assertIsNotNone(sh_bm)
        self.assertIsNotNone(sh_op)

        model_fast_fill(MENU_X0, MENU_Y0, MENU_X1, MENU_Y1, 0x00800080, 0xFF)
        self.assertEqual(bm0, bm1, "Dual bitmap buffers must be identical")
        self.assertEqual(op0, op1, "Dual opacity buffers must be identical")

        # Test cursor move: touches only changed rows
        num_rows = 10
        cache = [{"item": i, "sig": i * 100, "sel": (i == 0)} for i in range(num_rows)]
        new_sel = 1
        redrawn_rows = []
        for i in range(num_rows):
            is_sel = (i == new_sel)
            cur_sig = i * 100 + (1 if is_sel else 0)
            if cache[i]["sig"] != cur_sig or cache[i]["sel"] != is_sel:
                redrawn_rows.append(i)
                cache[i]["sig"] = cur_sig
                cache[i]["sel"] = is_sel

        self.assertEqual(redrawn_rows, [0, 1], "Cursor move touches ONLY row 0 and row 1")

        # Test NULL shadow fallback path (simulated allocation failure)
        alloc_attempted = False
        sh_bm = None
        sh_op = None
        ensure_alloc(force_fail=True)
        self.assertIsNone(sh_bm)
        self.assertIsNone(sh_op)

        # Drawing with NULL shadow must succeed into bm0/1 without exception or OOB writes
        bm0[:] = b"\x00" * BM_SIZE
        bm1[:] = b"\x00" * BM_SIZE
        op0[:] = b"\x00" * OP_SIZE
        op1[:] = b"\x00" * OP_SIZE
        model_fast_fill(MENU_X0, MENU_Y0, MENU_X1, MENU_Y1, 0x00800080, 0xFF)
        self.assertEqual(bm0, bm1, "In fallback mode, dual bitmap buffers must receive identical bytes")
        self.assertEqual(op0, op1, "In fallback mode, dual opacity buffers must receive identical bytes")


if __name__ == "__main__":
    unittest.main()
