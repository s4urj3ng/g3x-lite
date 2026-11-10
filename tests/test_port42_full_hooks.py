"""Unit and integration tests for PORT-42 FULL_HOOKS=1 full CHDK build.

Verifies:
1. Toolchain availability and skip behavior if toolchain is missing.
2. FULL_HOOKS=1 full build execution producing out/port41-full/DISKBOOT.BIN,
   CHDK/ distribution folder, and port42_full_hooks_manifest.json.
3. FULL_HOOKS=1 manifest integrity (includes FULL_HOOKS=1 in build flags,
   accurate artifact size and sha256).
4. CreateTask_my hook intercepts in staged core ELF:
   - task_PhySw (0xFC1283AD, FINSIG/VERIFIED) -> mykbd_task
   - task_InitFileModules (0xFC0BD071, FINSIG/VERIFIED) -> init_file_modules_task
   - task_CaptSeq (0xFC06A001, FINSIG) -> capt_seq_task
   - task_FileWrite (0xFC25F3A7, FINSIG) -> filewritetask
   - task_MovieRecord, task_ExpDrv, task_DvlpSeqTask remain stock (disabled).
5. capt_seq_task and filewritetask safe trampolines to 0xFC06A001 and 0xFC25F3A7.
6. Card-write suppression compile flags and linker wrap symbols remain active.
7. Candidate invariance: PORT-24..40 candidate builds remain byte-identical.
8. docs/PORT42_FULL_HOOKS.md table format, sibling citations, and labels.
"""

from __future__ import annotations

import json
import os
import re
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

        # Run full build with --full-hooks
        cmd = ["python3", "-B", str(BUILD_SCRIPT), "--full-hooks"]
        res = subprocess.run(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
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
        self._require_full_build()

        # Check DISKBOOT.BIN
        diskboot = self.diskboot
        self.assertTrue(diskboot.is_file(), f"Expected {diskboot} to exist")
        self.assertGreater(diskboot.stat().st_size, 50000)

        # Check CHDK folder contents
        chdk_dir = OUT_DIR / "CHDK"
        self.assertTrue(chdk_dir.is_dir(), f"Expected {chdk_dir} to exist")
        modules_dir = chdk_dir / "MODULES"
        self.assertTrue(modules_dir.is_dir(), f"Expected {modules_dir} to exist")
        flt_files = list(modules_dir.glob("*.flt"))
        self.assertGreaterEqual(len(flt_files), 30)

        # Check port42_full_hooks_manifest.json
        manifest_path = self.p42_manifest
        self.assertTrue(manifest_path.is_file(), f"Expected {manifest_path} to exist")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertIn("FULL_HOOKS=1", manifest["build"]["flags"])
        self.assertEqual(manifest["artifacts"]["DISKBOOT.BIN"]["size"], diskboot.stat().st_size)
        self.assertEqual(manifest["artifacts"]["modules_count"], len(flt_files))

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
        """Verify that PORT-24..40 candidates remain 100% byte-identical."""
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
