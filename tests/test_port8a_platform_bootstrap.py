"""PORT-8A: clean-checkout regression tests for tools/bootstrap_chdk_platform.py.

Tier 1 runs on any clean clone, writing only to temporary directories:
vendored baseline integrity, PORT-7B patch contract, create/idempotence,
verify-only, fail-closed conflicts (modified file, symlink, unexpected
preimage, tampered vendor copy, unsafe manifest path), changes made between
planning and writing (edit, save-by-rename, new file, symlinked directory,
second writer) and the PORT-7A constant checks on a bootstrapped tree. Tier 2 (skipped when the local
chdk-port/platform/g3x sources are absent) only reads the live workspace in
verify-only mode. No subprocess, compiler, ROM read or hardware access.

Run:
  python3 -B -m unittest discover -s tests -p test_port8a_platform_bootstrap.py -v
"""

import io
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import unittest
import unittest.mock

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "tools"))

import bootstrap_chdk_platform as boot  # noqa: E402
import test_port7a_platform_configuration as port7a  # noqa: E402
import test_port7b_reproducibility as port7b  # noqa: E402


MANIFEST = boot.DEFAULT_MANIFEST
VENDOR = MANIFEST.parent
EXPECTED_PATHS = [
    "platform/g3x/kbd.c", "platform/g3x/lib.c", "platform/g3x/platform_camera.h",
    "platform/g3x/platform_kbd.h", "platform/g3x/shooting.c",
]
KBD_H = "platform/g3x/platform_kbd.h"


def run_quiet(target, **kwargs):
    out = io.StringIO()
    code = boot.run(target, out=out, **kwargs)
    return code, out.getvalue()


def snapshot(root):
    root = Path(root)
    return {str(p.relative_to(root)): (p.read_bytes(), p.stat().st_mtime_ns)
            for p in sorted(root.rglob("*")) if p.is_file()}


class TempTargetCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory(prefix="port8a-")
        self.target = Path(self._tmp.name) / "chdk-port"
        self.target.mkdir()

    def tearDown(self):
        self._tmp.cleanup()

    def copy_vendor(self):
        """Writable copy of the vendor tree for tamper tests."""
        copy = Path(self._tmp.name) / "vendor"
        shutil.copytree(VENDOR, copy)
        return copy / "MANIFEST.json"


class TestVendoredBaseline(unittest.TestCase):
    def test_manifest_lists_exactly_the_minimal_source_set(self):
        manifest = boot.load_manifest(MANIFEST)
        self.assertEqual(sorted(e["path"] for e in manifest["files"]), EXPECTED_PATHS)
        self.assertEqual(manifest["firmware"], "GM1.10C")
        self.assertEqual(manifest["target_root"], "chdk-port")

    def test_vendor_tree_holds_only_manifest_files(self):
        files = sorted(str(p.relative_to(VENDOR)) for p in VENDOR.rglob("*") if p.is_file())
        self.assertEqual(files, sorted(["MANIFEST.json", *EXPECTED_PATHS]))

    def test_vendored_bytes_and_patch_contract_verify(self):
        expected = boot.build_expected(boot.load_manifest(MANIFEST), MANIFEST)
        self.assertEqual(boot.sha256(expected[KBD_H][0]), port7b.PRE_SHA)
        self.assertEqual(boot.sha256(expected[KBD_H][1]), port7b.POST_SHA)

    def test_vendor_preimage_is_the_port7b_fixture(self):
        self.assertEqual((VENDOR / KBD_H).read_bytes(), port7b.PREIMAGE.read_bytes())

    def test_port7b_excerpts_are_ranges_of_vendored_sources(self):
        for name, ranges in port7b.EXCERPTS.items():
            with self.subTest(name=name):
                lines = (VENDOR / "platform/g3x" / name).read_text(encoding="utf-8")
                lines = lines.splitlines(keepends=True)
                expected = "".join("".join(lines[a - 1:b]) for a, b in ranges)
                self.assertEqual((port7b.FIXTURES / name).read_text(encoding="utf-8"), expected)

    def test_bootstrapped_mask_is_the_port7b_correction(self):
        final = boot.build_expected(boot.load_manifest(MANIFEST), MANIFEST)[KBD_H][1]
        self.assertEqual(port7a.override_masks(final.decode("utf-8")), (0x000533F9, 0, 0))


class TestBootstrapBehaviour(TempTargetCase):
    def test_creates_only_manifest_files_with_final_hashes(self):
        code, out = run_quiet(self.target)
        self.assertEqual(code, 0, out)
        written = snapshot(self.target)
        self.assertEqual(sorted(written), EXPECTED_PATHS)
        manifest = boot.load_manifest(MANIFEST)
        for entry in manifest["files"]:
            self.assertEqual(boot.sha256(written[entry["path"]][0]), entry["final_sha256"])

    def test_second_run_is_idempotent_and_writes_nothing(self):
        self.assertEqual(run_quiet(self.target)[0], 0)
        before = snapshot(self.target)
        code, out = run_quiet(self.target)
        self.assertEqual(code, 0, out)
        self.assertNotIn("CREATE", out)
        self.assertEqual(snapshot(self.target), before)

    def test_verify_only_never_writes(self):
        code, out = run_quiet(self.target, verify_only=True)
        self.assertEqual(code, 1, out)
        self.assertEqual(snapshot(self.target), {})
        run_quiet(self.target)
        self.assertEqual(run_quiet(self.target, verify_only=True)[0], 0)

    def test_recorded_preimage_is_advanced_by_patch(self):
        dest = self.target / KBD_H
        dest.parent.mkdir(parents=True)
        shutil.copyfile(VENDOR / KBD_H, dest)
        code, out = run_quiet(self.target)
        self.assertEqual(code, 0, out)
        self.assertIn("ADVANCE", out)
        self.assertEqual(boot.sha256(dest.read_bytes()), port7b.POST_SHA)

    def test_modified_local_file_is_never_overwritten_and_nothing_is_written(self):
        dest = self.target / "platform/g3x/kbd.c"
        dest.parent.mkdir(parents=True)
        dest.write_bytes((VENDOR / "platform/g3x/kbd.c").read_bytes() + b"// local edit\n")
        before = snapshot(self.target)
        for verify_only in (False, True):
            with self.subTest(verify_only=verify_only):
                code, out = run_quiet(self.target, verify_only=verify_only)
                self.assertEqual(code, 2, out)
                self.assertIn("CONFLICT", out)
                self.assertEqual(snapshot(self.target), before)

    def test_symlinked_target_file_is_a_conflict(self):
        outside = Path(self._tmp.name) / "outside.c"
        outside.write_bytes(b"outside\n")
        dest = self.target / "platform/g3x/lib.c"
        dest.parent.mkdir(parents=True)
        dest.symlink_to(outside)
        code, out = run_quiet(self.target)
        self.assertEqual(code, 2, out)
        self.assertEqual(outside.read_bytes(), b"outside\n")
        self.assertFalse((self.target / "platform/g3x/kbd.c").exists())

    def test_missing_target_root_is_an_error(self):
        code, _ = run_quiet(self.target / "absent")
        self.assertEqual(code, 3)


class TestFailClosedIntegrity(TempTargetCase):
    def assert_integrity_error(self, manifest_path):
        code, out = run_quiet(self.target, manifest_path=manifest_path)
        self.assertEqual(code, 3, out)
        self.assertEqual(snapshot(self.target), {})

    def test_tampered_vendored_file_is_rejected(self):
        manifest = self.copy_vendor()
        path = manifest.parent / "platform/g3x/shooting.c"
        path.write_bytes(path.read_bytes().replace(b"32768", b"32769"))
        self.assert_integrity_error(manifest)

    def test_unexpected_patch_preimage_is_rejected(self):
        manifest = self.copy_vendor()
        data = json.loads(manifest.read_text())
        data["patches"][0]["preimage_sha256"] = "0" * 64
        manifest.write_text(json.dumps(data))
        self.assert_integrity_error(manifest)

    def test_vendored_postimage_instead_of_preimage_is_rejected(self):
        manifest = self.copy_vendor()
        expected = boot.build_expected(boot.load_manifest(MANIFEST), MANIFEST)
        (manifest.parent / KBD_H).write_bytes(expected[KBD_H][1])
        self.assert_integrity_error(manifest)

    def test_unsafe_manifest_paths_are_rejected(self):
        for bad in ("../escape.c", "/abs/kbd.c", "platform/../../x.c", "a\\b.c"):
            with self.subTest(path=bad):
                manifest = self.copy_vendor()
                data = json.loads(manifest.read_text())
                data["files"][0]["path"] = bad
                manifest.write_text(json.dumps(data))
                self.assert_integrity_error(manifest)
                shutil.rmtree(manifest.parent)


class TestConcurrentChangeDefences(TempTargetCase):
    """Changes made between planning and writing (PORT-8A review of 5a08a92)."""

    def setUp(self):
        super().setUp()
        self.expected = boot.build_expected(boot.load_manifest(MANIFEST), MANIFEST)

    def execute(self, steps):
        root_fd = os.open(self.target, boot.DIR_FLAGS)
        try:
            boot.execute(root_fd, self.expected, steps)
        finally:
            os.close(root_fd)

    def place_preimage(self):
        dest = self.target / KBD_H
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(VENDOR / KBD_H, dest)
        return dest

    def assert_no_scratch_files(self):
        self.assertEqual([p.name for p in self.target.rglob(".bootstrap-*")], [])

    def test_baseline_edited_after_planning_is_restored_not_overwritten(self):
        dest = self.place_preimage()
        steps = boot.plan(self.target, self.expected)
        self.assertIn((KBD_H, boot.ADVANCE), [(r, s) for r, s, _ in steps])
        edited = dest.read_bytes() + b"// concurrent edit\n"
        dest.write_bytes(edited)
        with self.assertRaises(boot.ConflictError):
            self.execute([s for s in steps if s[0] == KBD_H])
        self.assertEqual(dest.read_bytes(), edited)
        self.assert_no_scratch_files()

    def test_save_by_rename_during_advance_is_kept(self):
        dest = self.place_preimage()
        saved = b"// editor saved while bootstrap was running\n"
        original = boot._read_nofollow

        def read_then_editor_saves(name, dir_fd):
            data = original(name, dir_fd)
            dest.write_bytes(saved)  # name was free after the rename-aside
            return data

        with unittest.mock.patch.object(boot, "_read_nofollow", read_then_editor_saves):
            code, out = run_quiet(self.target)
        self.assertEqual(code, 2, out)
        self.assertIn("CONFLICT", out)
        self.assertEqual(dest.read_bytes(), saved)
        self.assert_no_scratch_files()

    def test_file_created_after_planning_is_not_overwritten(self):
        steps = boot.plan(self.target, self.expected)
        dest = self.target / "platform/g3x/kbd.c"
        dest.parent.mkdir(parents=True)
        dest.write_bytes(b"created concurrently\n")
        with self.assertRaises(boot.ConflictError):
            self.execute([s for s in steps if s[0] == "platform/g3x/kbd.c"])
        self.assertEqual(dest.read_bytes(), b"created concurrently\n")
        self.assert_no_scratch_files()

    def test_directory_swapped_for_symlink_after_planning_writes_nothing_outside(self):
        steps = boot.plan(self.target, self.expected)
        outside = Path(self._tmp.name) / "outside"
        outside.mkdir()
        (self.target / "platform").symlink_to(outside, target_is_directory=True)
        with self.assertRaises(boot.ConflictError):
            self.execute(steps)
        self.assertEqual(list(outside.rglob("*")), [])

    def test_second_writer_is_locked_out(self):
        holder = os.open(self.target, boot.DIR_FLAGS)
        try:
            boot.fcntl.flock(holder, boot.fcntl.LOCK_EX | boot.fcntl.LOCK_NB)
            code, out = run_quiet(self.target)
            self.assertEqual(code, 2, out)
            self.assertIn("lock", out)
            self.assertEqual(snapshot(self.target), {})
            self.assertEqual(run_quiet(self.target, verify_only=True)[0], 1)
        finally:
            os.close(holder)
        self.assertEqual(run_quiet(self.target)[0], 0)


class TestPort7aChecksOnBootstrappedTree(port7a.TestRecordedGm110cConstants):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="port8a-7a-")
        target = Path(cls._tmp.name)
        code, out = run_quiet(target)
        if code != 0:
            raise RuntimeError(out)
        cls.sources = port7a.load_sources(target / "platform/g3x")
        cls.keys = port7a.keymap(cls.sources['kbd.c'])
        cls.camera = cls.sources['platform_camera.h']
        cls.header = cls.sources['platform_kbd.h']

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()


@unittest.skipUnless((REPO_ROOT / "chdk-port/platform/g3x/kbd.c").is_file(),
                     "local chdk-port/platform/g3x sources not present (clean checkout)")
class TestLiveWorkspaceVerifyOnly(unittest.TestCase):
    def test_live_sources_are_at_final_hashes(self):
        code, out = run_quiet(None, verify_only=True)
        self.assertEqual(code, 0, out)


if __name__ == "__main__":
    unittest.main()
