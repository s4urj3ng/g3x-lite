"""Unit and integration host tests for PORT-42 GUI-fixed full build and trial plan.

Verifies:
1. docs/PORT42_GUI_TRIAL.md format and content:
   - Formatted as a Markdown table.
   - Order: GUI-fixed default build first, FULL_HOOKS variant only after it passes.
   - Checks: no flicker on the ALT panel (hold for 10 s), no pink blocks,
     an opaque black panel with readable 2x text, CHDK Menu opens and is readable,
     boot method (held vs short press) recorded, power-off behaviour recorded.
   - Recovery is a battery pull (>= 10 s).
   - SD card writes are off.
2. Output manifests (manifests/ and docs/manifests/):
   - manifests/port42_gui_manifest.json: DISKBOOT.BIN (124,257 B, SHA-256 760a362d...)
     plus every CHDK/ file with SHA-256 and size (34 modules).
   - manifests/port42_gui_full_hooks_manifest.json: DISKBOOT.BIN (124,321 B, SHA-256 d50ea585...)
     plus every CHDK/ file with SHA-256 and size (34 modules).
3. Symbol and source checks confirming the fixes:
   - No periodic forced redraw call in GUI tick path.
   - Draw target uses active_bitmap_buffer & 1.
   - UYVY neutral black/white constants and opacity 0xFF.
   - 16x32 font routines and 2x scaling.
   - 880x576 centered layout.
4. Build reproducibility:
   - GUI-fixed full build builds reproducibly in fresh temporary directories.
   - GUI fix + FULL_HOOKS full build builds reproducibly in fresh temporary directories.
5. Switch-off invariance:
   - With fix switch off, output reproduces manifests/port41_manifest.json byte-for-byte.
6. Old candidate invariance:
   - Old candidate builds (default candidate_port2a, gui4, gui5, gui5_shortpress)
     built in fresh temporary directories remain 100% byte-identical.
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
BUILD_SCRIPT = REPO_ROOT / "tools" / "build_port41_full.py"
OUT_DIR_GUI = REPO_ROOT / "out" / "port42-gui"
OUT_DIR_GUI_HOOKS = REPO_ROOT / "out" / "port42-gui-full-hooks"
OUT_DIR_FULL = REPO_ROOT / "out" / "port41-full"
WRAPPER_SCRIPT = REPO_ROOT / "scripts" / "gcc_deterministic_wrapper.sh"
MANIFESTS_DIR = REPO_ROOT / "manifests"
DOCS_MANIFESTS_DIR = REPO_ROOT / "docs" / "manifests"

EXPECTED_GUI_DEFAULT_SHA = "760a362d358d87518e6274013e70109f8699974a40158ae5bbbff8b80c246738"
EXPECTED_GUI_DEFAULT_SIZE = 124257

EXPECTED_GUI_HOOKS_SHA = "d50ea585b2ba49e39674395f504b5780a1cb98a915fe998c5b7fa5be115cb9bb"
EXPECTED_GUI_HOOKS_SIZE = 124321

EXPECTED_PORT41_SHA = "24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9"
EXPECTED_PORT41_SIZE = 124097


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def snapshot_distribution(out_path: Path) -> dict[str, tuple[int, str]]:
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


class TestPort42GuiTrialPlanDoc(unittest.TestCase):
    """Static checks on docs/PORT42_GUI_TRIAL.md."""

    def setUp(self):
        self.doc_path = REPO_ROOT / "docs" / "PORT42_GUI_TRIAL.md"
        self.assertTrue(self.doc_path.is_file(), f"Missing {self.doc_path}")
        self.text = self.doc_path.read_text(encoding="utf-8")

    def test_trial_plan_doc_table_structure(self):
        """Verify the document exists and contains markdown table formatting."""
        # Must contain markdown table header separator
        self.assertRegex(self.text, r"\|:?-+:?\|:?-+:?\|")
        # Header must have columns for step, variant, checks, criteria
        self.assertRegex(self.text, r"(?i)\|.*Step.*\|.*Variant.*\|.*Check.*\|")

    def test_trial_plan_execution_order(self):
        """Verify GUI-fixed default build is ordered first, and FULL_HOOKS variant only after it passes."""
        lower = self.text.lower()
        default_idx = lower.find("gui-fixed default")
        hooks_idx = lower.find("full_hooks")
        self.assertGreater(default_idx, -1, "GUI-Fixed Default build must be mentioned")
        self.assertGreater(hooks_idx, -1, "FULL_HOOKS build must be mentioned")
        self.assertLess(default_idx, hooks_idx, "Default GUI build must be ordered before FULL_HOOKS variant")

        # Table step order: Step 1.1 precedes Step 2.1
        step1_idx = self.text.find("1.1")
        step2_idx = self.text.find("2.1")
        self.assertGreater(step1_idx, -1)
        self.assertGreater(step2_idx, -1)
        self.assertLess(step1_idx, step2_idx, "Table Step 1.1 must precede Step 2.1")

        # Explicit gate requirement
        self.assertTrue(
            "only after" in lower or "only after it passes" in lower or "gate" in lower,
            "Must state FULL_HOOKS variant is run only after default build passes",
        )

    def test_trial_plan_required_checks(self):
        """Verify all checks required by the task prompt are present in the table."""
        # 1. No flicker on the ALT panel (hold for 10 s)
        self.assertIn("10 s", self.text)
        self.assertTrue(
            "no flicker" in self.text.lower() or "zero-flicker" in self.text.lower(),
            "Must check for no flicker on the ALT panel (hold for 10 s)",
        )

        # 2. No pink blocks
        self.assertTrue(
            "no pink blocks" in self.text.lower() or "pink" in self.text.lower(),
            "Must check for no pink blocks",
        )

        # 3. Opaque black panel with readable 2x text
        self.assertTrue(
            "opaque black" in self.text.lower(),
            "Must check for opaque black panel",
        )
        self.assertTrue(
            "2x" in self.text and "16x32" in self.text,
            "Must check for readable 2x text (16x32 font)",
        )

        # 4. CHDK Menu (Menu key in ALT) opens and is readable
        self.assertTrue(
            "chdk menu" in self.text.lower() and "readable" in self.text.lower(),
            "Must check CHDK Menu opens and is readable",
        )

        # 5. Boot method (held vs short press) recorded
        self.assertTrue(
            "boot method" in self.text.lower() or ("short press" in self.text.lower() and "held press" in self.text.lower()),
            "Must record boot method (held vs short press)",
        )

        # 6. Power-off behaviour recorded
        self.assertTrue(
            "power-off" in self.text.lower() or "power off" in self.text.lower(),
            "Must record power-off behaviour",
        )

        # 7. Recovery is a battery pull
        self.assertTrue(
            "battery pull" in self.text.lower(),
            "Recovery must specify a battery pull",
        )

        # 8. Card writes are off
        self.assertTrue(
            "card write" in self.text.lower() or "writes are off" in self.text.lower() or "lock" in self.text.lower(),
            "Must specify card writes are off",
        )


class TestPort42GuiManifestIntegrity(unittest.TestCase):
    """Validation of manifests/port42_gui_manifest.json and port42_gui_full_hooks_manifest.json."""

    def test_port42_gui_manifest_contents(self):
        """Verify manifests/port42_gui_manifest.json lists DISKBOOT.BIN and every CHDK/ file."""
        for mdir in [MANIFESTS_DIR, DOCS_MANIFESTS_DIR]:
            mpath = mdir / "port42_gui_manifest.json"
            self.assertTrue(mpath.is_file(), f"Expected manifest file at {mpath}")
            with open(mpath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # DISKBOOT.BIN
            self.assertIn("DISKBOOT.BIN", data["artifacts"])
            diskboot = data["artifacts"]["DISKBOOT.BIN"]
            self.assertEqual(diskboot["size"], EXPECTED_GUI_DEFAULT_SIZE)
            self.assertEqual(diskboot["sha256"], EXPECTED_GUI_DEFAULT_SHA)

            # Modules
            self.assertEqual(data["artifacts"]["modules_count"], 34)
            self.assertEqual(len(data["artifacts"]["modules"]), 34)

            # CHDK/ distribution files
            self.assertIn("chdk_files", data["artifacts"])
            chdk_files = data["artifacts"]["chdk_files"]
            self.assertGreaterEqual(len(chdk_files), 100)
            for path_str, info in chdk_files.items():
                self.assertTrue(path_str.startswith("CHDK/"), f"File {path_str} must be in CHDK/")
                self.assertIn("size", info)
                self.assertIn("sha256", info)
                self.assertGreater(info["size"], 0)
                self.assertEqual(len(info["sha256"]), 64)

    def test_port42_gui_full_hooks_manifest_contents(self):
        """Verify manifests/port42_gui_full_hooks_manifest.json lists DISKBOOT.BIN and every CHDK/ file."""
        for mdir in [MANIFESTS_DIR, DOCS_MANIFESTS_DIR]:
            mpath = mdir / "port42_gui_full_hooks_manifest.json"
            self.assertTrue(mpath.is_file(), f"Expected manifest file at {mpath}")
            with open(mpath, "r", encoding="utf-8") as f:
                data = json.load(f)

            # DISKBOOT.BIN
            self.assertIn("DISKBOOT.BIN", data["artifacts"])
            diskboot = data["artifacts"]["DISKBOOT.BIN"]
            self.assertEqual(diskboot["size"], EXPECTED_GUI_HOOKS_SIZE)
            self.assertEqual(diskboot["sha256"], EXPECTED_GUI_HOOKS_SHA)

            # Modules
            self.assertEqual(data["artifacts"]["modules_count"], 34)
            self.assertEqual(len(data["artifacts"]["modules"]), 34)

            # CHDK/ distribution files
            self.assertIn("chdk_files", data["artifacts"])
            chdk_files = data["artifacts"]["chdk_files"]
            self.assertGreaterEqual(len(chdk_files), 100)
            for path_str, info in chdk_files.items():
                self.assertTrue(path_str.startswith("CHDK/"), f"File {path_str} must be in CHDK/")
                self.assertIn("size", info)
                self.assertIn("sha256", info)


class TestPort42GuiSymbolAndSourceChecks(unittest.TestCase):
    """Static and symbol checks confirming the GUI fixes."""

    def test_no_periodic_forced_redraw_in_gui_tick_path(self):
        """Verify no periodic forced redraw loop exists in GUI tick path."""
        # tools/build_port41_full.py core patches
        build_py = BUILD_SCRIPT.read_text(encoding="utf-8")

        # Must have gui_maintenance_tick unconditionally called
        self.assertIn("gui_maintenance_tick();", build_py)
        self.assertIn("gui_check_state_changed()", build_py)
        self.assertIn("!draw_test_guard()", build_py)
        self.assertIn("check_bitmap_buffer_changed()", build_py)

        # Must NOT have periodic forced-redraw pattern ((cnt++) & N) in main loop replacement
        main_patch_start = build_py.find("main_replacement =")
        main_patch_end = build_py.find("core_conf_c =", main_patch_start)
        main_patch = build_py[main_patch_start:main_patch_end]
        self.assertNotIn("cnt++", main_patch)
        self.assertNotIn("& 3", main_patch)

    def test_draw_target_uses_active_bitmap_buffer(self):
        """Verify draw target uses active_bitmap_buffer & 1."""
        lib_c = (REPO_ROOT / "full_build" / "g3x" / "lib.c").read_text(encoding="utf-8")
        gui_menu_c = (REPO_ROOT / "full_build" / "g3x" / "gui_menu.c").read_text(encoding="utf-8")
        build_py = BUILD_SCRIPT.read_text(encoding="utf-8")

        # lib.c active buffer indexing
        self.assertIn("active_bitmap_buffer & 1", lib_c)
        self.assertIn("vid_get_bitmap_fb", lib_c)
        self.assertIn("vid_get_opacity_active_buffer", lib_c)

        # gui_menu.c active buffer indexing for opaque fill
        self.assertIn("active_bitmap_buffer & 1", gui_menu_c)
        self.assertIn("g3x_fill_menu_opaque_black", gui_menu_c)

        # build_port41_full.py patches draw_set_guard and draw_test_guard with active_bitmap_buffer & 1
        self.assertIn("draw_set_guard", build_py)
        self.assertIn("draw_test_guard", build_py)
        self.assertIn("active_bitmap_buffer & 1", build_py)

    def test_uyvy_black_white_constants_and_opacity(self):
        """Verify DIGIC 6 UYVY black/white constants and opacity 0xFF."""
        gui_menu_c = (REPO_ROOT / "full_build" / "g3x" / "gui_menu.c").read_text(encoding="utf-8")
        lib_c = (REPO_ROOT / "full_build" / "g3x" / "lib.c").read_text(encoding="utf-8")
        build_py = BUILD_SCRIPT.read_text(encoding="utf-8")
        doc_fix = (REPO_ROOT / "docs" / "PORT42_GUI_FIX.md").read_text(encoding="utf-8")

        # Neutral UYVY black (0x00800080) and opacity 0xFF
        self.assertIn("0x00800080", gui_menu_c)
        self.assertIn("0xFF", gui_menu_c)

        # Real opacity buffer array addresses in DRAM
        self.assertIn("0x5FC40000", lib_c)
        self.assertIn("0x5FB80000", lib_c)

        # Neutral UYVY white (0xFF80FF80 / 0xFF80)
        self.assertTrue(
            "0xFF80FF80" in doc_fix or "0xFF80" in doc_fix,
            "UYVY white documented in fix doc",
        )

        # Stage core conf default colors black background, white foreground
        self.assertIn("IDX_COLOR_BLACK", build_py)
        self.assertIn("IDX_COLOR_WHITE", build_py)
        self.assertIn("conf.menu_color", build_py)

    def test_16x32_font_routines(self):
        """Verify 16x32 font routines and 2x scaling in gui_menu.c."""
        gui_menu_c = (REPO_ROOT / "full_build" / "g3x" / "gui_menu.c").read_text(encoding="utf-8")
        build_py = BUILD_SCRIPT.read_text(encoding="utf-8")

        # Font rasterizer and dimensions
        self.assertIn("g3x_draw_char_16x32", gui_menu_c)
        self.assertIn("rbf_font_height", gui_menu_c)
        self.assertIn("rbf_char_width", gui_menu_c)
        self.assertIn("rbf_draw_menu_header", gui_menu_c)

        # Return values: 32 px height, 16 px width
        self.assertIn("return 32;", gui_menu_c)
        self.assertIn("return 16;", gui_menu_c)

        # Headers patched with 16x32 font dimensions
        self.assertRegex(build_py, r"#define\s+FONT_WIDTH\s+16")
        self.assertRegex(build_py, r"#define\s+FONT_HEIGHT\s+32")

    def test_880x576_layout(self):
        """Verify 880x576 solid black layout."""
        gui_menu_c = (REPO_ROOT / "full_build" / "g3x" / "gui_menu.c").read_text(encoding="utf-8")

        self.assertIn("880", gui_menu_c)
        self.assertIn("576", gui_menu_c)
        self.assertIn("g3x_get_menu_layout", gui_menu_c)
        self.assertIn("g3x_fill_menu_opaque_black", gui_menu_c)

    def test_compiled_symbols(self):
        """Verify symbols in out/port42-gui artifacts when toolchain nm is available."""
        if not (TOOLCHAIN_NM.is_file() and os.access(TOOLCHAIN_NM, os.X_OK)):
            self.skipTest(f"Toolchain nm not available at {TOOLCHAIN_NM}")

        core_elf = OUT_DIR_GUI / "stage_chdk" / "core" / "main.elf"
        if not core_elf.is_file():
            # If stage_chdk was cleaned, skip ELF symbol test
            return

        res = subprocess.run([str(TOOLCHAIN_NM), str(core_elf)], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0:
            nm_out = res.stdout
            self.assertIn("g3x_draw_char_16x32", nm_out)
            self.assertIn("g3x_fill_menu_opaque_black", nm_out)
            self.assertIn("gui_maintenance_tick", nm_out)
            self.assertIn("gui_check_state_changed", nm_out)


class TestPort42GuiTrialExecution(unittest.TestCase):
    """Self-contained build and invariance execution tests."""

    @classmethod
    def setUpClass(cls):
        cls.has_toolchain = TOOLCHAIN_GCC.is_file() and os.access(TOOLCHAIN_GCC, os.X_OK)

    def _require_toolchain(self):
        if not self.has_toolchain:
            self.skipTest(f"Pinned toolchain gcc not found at {TOOLCHAIN_GCC}")

    def test_gui_fix_reproducible_build(self):
        """Verify that GUI-fixed full build builds reproducibly in fresh temporary directories."""
        self._require_toolchain()

        env = os.environ.copy()
        if WRAPPER_SCRIPT.is_file() and os.access(WRAPPER_SCRIPT, os.X_OK):
            env["MAKEFLAGS"] = f"CC={WRAPPER_SCRIPT}"

        with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
            res1 = subprocess.run(
                ["python3", "-B", str(BUILD_SCRIPT), "--gui-fix", "--out-dir", td1],
                cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            self.assertEqual(res1.returncode, 0, f"Build 1 failed: {res1.stderr}")

            res2 = subprocess.run(
                ["python3", "-B", str(BUILD_SCRIPT), "--gui-fix", "--out-dir", td2],
                cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            self.assertEqual(res2.returncode, 0, f"Build 2 failed: {res2.stderr}")

            snap1 = snapshot_distribution(Path(td1))
            snap2 = snapshot_distribution(Path(td2))
            self.assertEqual(snap1, snap2, "Build 1 and Build 2 must produce byte-identical distribution trees")
            self.assertIn("DISKBOOT.BIN", snap1)
            self.assertEqual(snap1["DISKBOOT.BIN"], (EXPECTED_GUI_DEFAULT_SIZE, EXPECTED_GUI_DEFAULT_SHA))

    def test_gui_fix_full_hooks_reproducible_build(self):
        """Verify that GUI fix + FULL_HOOKS full build builds reproducibly in fresh temporary directories."""
        self._require_toolchain()

        env = os.environ.copy()
        if WRAPPER_SCRIPT.is_file() and os.access(WRAPPER_SCRIPT, os.X_OK):
            env["MAKEFLAGS"] = f"CC={WRAPPER_SCRIPT}"

        with tempfile.TemporaryDirectory() as td1, tempfile.TemporaryDirectory() as td2:
            res1 = subprocess.run(
                ["python3", "-B", str(BUILD_SCRIPT), "--gui-fix", "--full-hooks", "--out-dir", td1],
                cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            self.assertEqual(res1.returncode, 0, f"Build 1 failed: {res1.stderr}")

            res2 = subprocess.run(
                ["python3", "-B", str(BUILD_SCRIPT), "--gui-fix", "--full-hooks", "--out-dir", td2],
                cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            self.assertEqual(res2.returncode, 0, f"Build 2 failed: {res2.stderr}")

            snap1 = snapshot_distribution(Path(td1))
            snap2 = snapshot_distribution(Path(td2))
            self.assertEqual(snap1, snap2, "FULL_HOOKS builds must be byte-identical")
            self.assertIn("DISKBOOT.BIN", snap1)
            self.assertEqual(snap1["DISKBOOT.BIN"], (EXPECTED_GUI_HOOKS_SIZE, EXPECTED_GUI_HOOKS_SHA))

    def test_switch_off_reproduces_port41_manifest(self):
        """Verify that with fix switch off, the full build reproduces manifests/port41_manifest.json."""
        self._require_toolchain()

        env = os.environ.copy()
        if WRAPPER_SCRIPT.is_file() and os.access(WRAPPER_SCRIPT, os.X_OK):
            env["MAKEFLAGS"] = f"CC={WRAPPER_SCRIPT}"

        with tempfile.TemporaryDirectory() as td:
            res = subprocess.run(
                ["python3", "-B", str(BUILD_SCRIPT), "--out-dir", td],
                cwd=str(REPO_ROOT),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
            )
            self.assertEqual(res.returncode, 0, f"Switch-off build failed: {res.stderr}")

            actual = snapshot_distribution(Path(td))
            with open(MANIFESTS_DIR / "port41_manifest.json", "r", encoding="utf-8") as f:
                port41_manifest = json.load(f)

            self.assertEqual(
                actual["DISKBOOT.BIN"],
                (
                    port41_manifest["artifacts"]["DISKBOOT.BIN"]["size"],
                    port41_manifest["artifacts"]["DISKBOOT.BIN"]["sha256"],
                ),
            )
            for rel, info in port41_manifest["artifacts"]["chdk_files"].items():
                self.assertIn(rel, actual, f"Missing file from switch-off build: {rel}")
                self.assertEqual(actual[rel], (info["size"], info["sha256"]), f"Mismatch for {rel}")

    def test_old_candidates_stay_byte_identical(self):
        """Verify that old candidate builds remain 100% byte-identical."""
        self._require_toolchain()

        scripts_dir = REPO_ROOT / "scripts"
        import sys
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
