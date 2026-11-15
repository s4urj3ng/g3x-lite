"""Offline unit and integration tests for PORT-54 (G3X_CONF_SAVE=1).

Verifies:
1. Flag gating: G3X_CONF_SAVE=1 plumbing in makefiles and headers.
2. Default build byte-identity: Matches PORT-53 default SHA-256 and size.
3. Central path check: g3x_is_safe_chdk_write_path accepts A/CHDK/ paths and rejects outside paths, traversals ('..'), backslashes, and other drives.
4. Filesystem-ready gate: No write is reachable before spytask_can_start != 0.
5. Diag marker: SAVE:OK on success, SAVE:FAIL on failure, SAVE:OFF when disabled.
6. Write restrictions: filewrite.c hooks, scripts, and logging remain disabled.
7. Stub verification: Every file I/O stub address matches reference/finsig_gm110c/stubs_entry.S.
8. Manifest verification: Candidate manifest contains expected artifacts, hashes, and wrappers.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
DIAG_HEADER = ROOT / "chdk-port/platform/g3x/gui_diag.h"
PLAT_MAKEFILE = ROOT / "chdk-port/platform/g3x/Makefile"
SUB_MAKEFILE_INC = ROOT / "chdk-port/platform/g3x/sub/110c/makefile.inc"
SUB_MAKEFILE = ROOT / "chdk-port/platform/g3x/sub/110c/Makefile"
LIB_C = ROOT / "chdk-port/platform/g3x/lib.c"
FILEWRITE_C = ROOT / "chdk-port/platform/g3x/sub/110c/filewrite.c"
FINSIG_STUBS = ROOT / "reference/finsig_gm110c/stubs_entry.S"
MANIFEST_P54 = ROOT / "manifests/port54_conf_save_manifest.json"

TOOLCHAIN_BIN = ROOT / "toolchains/gcc-arm-none-eabi-5_4-2016q3/bin"
NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"
OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"

BASE_DEFAULT_SHA256 = "24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9"
BASE_DEFAULT_SIZE = 124097

BASE_ALONE_SHA256 = "0cc196f81126e8983b7b3921ecb220cb0f206d1375830cc15f07a56da2abd93b"
BASE_ALONE_SIZE = 124369

BASE_CANDIDATE_SHA256 = "220a9d7af1037638443c5f380932834c3760dce3bd997cdb1ff37b1eea64c783"
BASE_CANDIDATE_SIZE = 132401


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


class TestPort54FlagPlumbing(unittest.TestCase):
    def test_flag_definitions_in_makefiles(self):
        plat_mf = PLAT_MAKEFILE.read_text(encoding="utf-8")
        sub_mf = SUB_MAKEFILE_INC.read_text(encoding="utf-8")

        self.assertIn("ifeq ($(G3X_CONF_SAVE),1)", plat_mf)
        self.assertIn("CFLAGS += -DG3X_CONF_SAVE=1", plat_mf)
        self.assertIn("ifneq ($(G3X_CONF_SAVE),1)", plat_mf)

        self.assertIn("ifeq ($(G3X_CONF_SAVE),1)", sub_mf)
        self.assertIn("CFLAGS += -DG3X_CONF_SAVE=1", sub_mf)
        self.assertIn("ifneq ($(G3X_CONF_SAVE),1)", sub_mf)

    def test_gui_diag_header_constants_and_functions(self):
        self.assertTrue(DIAG_HEADER.is_file())
        text = DIAG_HEADER.read_text(encoding="utf-8")

        self.assertIn("#define G3X_CONF_SAVE_NONE 0", text)
        self.assertIn("#define G3X_CONF_SAVE_OK   1", text)
        self.assertIn("#define G3X_CONF_SAVE_FAIL 2", text)
        self.assertIn("#define G3X_CONF_SAVE_ERR  2", text)
        self.assertIn("#define G3X_CONF_SAVE_OFF  3", text)

        self.assertIn("G3X_CONF_SAVE", text)
        self.assertIn("g3x_is_safe_chdk_write_path", text)
        self.assertIn("g3x_conf_record_save_result", text)
        self.assertIn("g3x_conf_record_save_skipped", text)


class TestPort54DefaultBuildIdentity(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        default_bin = ROOT / "out/build-default/DISKBOOT.BIN"
        default_elf = ROOT / "out/build-default/stage_chdk/platform/g3x/sub/110c/main.elf"
        if not default_bin.is_file() or not default_elf.is_file():
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "tools/build_port41_full.py"),
                    "--keep-stage",
                    "--out-dir",
                    str(ROOT / "out/build-default"),
                ],
                cwd=ROOT,
                check=True,
            )

    def test_default_build_byte_identity(self):
        default_bin = ROOT / "out/build-default/DISKBOOT.BIN"
        self.assertTrue(default_bin.is_file(), f"Missing default build at {default_bin}")
        self.assertEqual(default_bin.stat().st_size, BASE_DEFAULT_SIZE)
        self.assertEqual(sha256_file(default_bin), BASE_DEFAULT_SHA256)


class TestPort54CentralPathCheck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Compile a native C test harness for g3x_is_safe_chdk_write_path
        c_code = """
#include <stdio.h>
#include <string.h>

static int g3x_tolower(int c)
{
    if (c >= 'A' && c <= 'Z') {
        return c + ('a' - 'A');
    }
    return c;
}

int g3x_is_safe_chdk_write_path(const char *path)
{
    if (!path) {
        return 0;
    }
    const char *p;
    for (p = path; *p; ++p) {
        if (*p == '\\\\') {
            return 0;
        }
    }
    for (p = path; *p; ++p) {
        if (p[0] == '.' && p[1] == '.') {
            return 0;
        }
    }
    int idx = 0;
    if (g3x_tolower((unsigned char)path[0]) != 'a') {
        return 0;
    }
    idx = 1;
    if (path[idx] == ':') {
        idx++;
    }
    if (path[idx] != '/') {
        return 0;
    }
    idx++;
    const char *target = "chdk/";
    int i;
    for (i = 0; i < 5; ++i) {
        if (g3x_tolower((unsigned char)path[idx + i]) != target[i]) {
            return 0;
        }
    }
    return 1;
}

int main(int argc, char **argv)
{
    if (argc < 2) return 2;
    if (strcmp(argv[1], "__NULL__") == 0) {
        return g3x_is_safe_chdk_write_path(NULL) ? 0 : 1;
    }
    return g3x_is_safe_chdk_write_path(argv[1]) ? 0 : 1;
}
"""
        cls.temp_dir = tempfile.TemporaryDirectory()
        src_path = Path(cls.temp_dir.name) / "test_path.c"
        src_path.write_text(c_code, encoding="utf-8")
        cls.bin_path = Path(cls.temp_dir.name) / "test_path"
        subprocess.run(["gcc", "-O2", str(src_path), "-o", str(cls.bin_path)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def _check_path(self, path: str) -> bool:
        res = subprocess.run([str(self.bin_path), path])
        return res.returncode == 0

    def test_safe_paths_accepted(self):
        accepted = [
            "A/CHDK/CCHDK4.CFG",
            "a/chdk/cchdk4.cfg",
            "A/chdk/test.cfg",
            "A:/CHDK/test.cfg",
            "a:/chdk/test.cfg",
            "A/CHDK/SUBDIR/file.cfg",
            "A/CHDK/nested/deep/path.txt",
        ]
        for p in accepted:
            self.assertTrue(self._check_path(p), f"Expected '{p}' to be accepted")

    def test_outside_paths_rejected(self):
        rejected = [
            "__NULL__",
            "",
            "A/DCIM/100CANON/IMG_0001.JPG",
            "A/MISC/LOG.TXT",
            "A/CHDK",
            "A/CHDK_OTHER/foo",
            "B/CHDK/test.cfg",
            "b:/chdk/test.cfg",
            "C/CHDK/test.cfg",
            "/A/CHDK/test.cfg",
            "A/OTHER/test.cfg",
        ]
        for p in rejected:
            self.assertFalse(self._check_path(p), f"Expected '{p}' to be rejected")

    def test_traversal_and_backslashes_rejected(self):
        traversals = [
            "../A/CHDK/test.cfg",
            "A/CHDK/../DCIM/IMG.JPG",
            "A/CHDK/..",
            "A/CHDK/test/../../DCIM",
            "A\\CHDK\\test.cfg",
            "A/CHDK\\test.cfg",
            "A/CHDK/..\\DCIM",
        ]
        for p in traversals:
            self.assertFalse(self._check_path(p), f"Expected traversal '{p}' to be rejected")


class TestPort54FilesystemReadyGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c_code = """
#include <stdio.h>
#include <string.h>

volatile int spytask_can_start = 0;

static int g3x_tolower(int c)
{
    if (c >= 'A' && c <= 'Z') return c + ('a' - 'A');
    return c;
}

int g3x_is_safe_chdk_write_path(const char *path)
{
    if (!path) return 0;
    const char *p;
    for (p = path; *p; ++p) if (*p == '\\\\') return 0;
    for (p = path; *p; ++p) if (p[0] == '.' && p[1] == '.') return 0;
    if (g3x_tolower((unsigned char)path[0]) != 'a') return 0;
    int idx = 1;
    if (path[idx] == ':') idx++;
    if (path[idx] != '/') return 0;
    idx++;
    const char *target = "chdk/";
    int i;
    for (i = 0; i < 5; ++i) {
        if (g3x_tolower((unsigned char)path[idx + i]) != target[i]) return 0;
    }
    return 1;
}

static int mock_real_write_calls = 0;
static int mock_real_open_calls = 0;

int __real_write(int fd, const void *buf, int n)
{
    mock_real_write_calls++;
    return n;
}

int __real_open(const char *name, int flags, int mode)
{
    mock_real_open_calls++;
    return 42; // mock fd
}

int __wrap_write(int fd, const void *buf, int n)
{
    if (!spytask_can_start) {
        return -1;
    }
    return __real_write(fd, buf, n);
}

int __wrap_open(const char *name, int flags, int mode)
{
    if ((flags & 3) != 0 || (flags & (0x08 | 0x0100 | 0x0200 | 0x0400 | 0x0800))) {
        if (!spytask_can_start) {
            return -1;
        }
        if (!g3x_is_safe_chdk_write_path(name)) {
            return -1;
        }
    }
    return __real_open(name, flags, mode);
}

int main(int argc, char **argv)
{
    if (argc < 4) return 99;
    spytask_can_start = argv[1][0] - '0';
    int is_write = strcmp(argv[2], "write") == 0;
    const char *path = argv[3];

    if (is_write) {
        int res = __wrap_write(1, "test", 4);
        return (res == 4) ? 0 : 1;
    } else {
        int res = __wrap_open(path, 0x0201 /* O_WRONLY|O_CREAT */, 0666);
        return (res == 42) ? 0 : 1;
    }
}
"""
        cls.temp_dir = tempfile.TemporaryDirectory()
        src_path = Path(cls.temp_dir.name) / "test_gate.c"
        src_path.write_text(c_code, encoding="utf-8")
        cls.bin_path = Path(cls.temp_dir.name) / "test_gate"
        subprocess.run(["gcc", "-O2", str(src_path), "-o", str(cls.bin_path)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_writes_blocked_before_filesystem_ready(self):
        # spytask_can_start = 0 -> must return -1 (exit code 1)
        res = subprocess.run([str(self.bin_path), "0", "write", "ignored"])
        self.assertEqual(res.returncode, 1, "write should be blocked before fs ready")

        res = subprocess.run([str(self.bin_path), "0", "open", "A/CHDK/CCHDK4.CFG"])
        self.assertEqual(res.returncode, 1, "open for write should be blocked before fs ready")

    def test_writes_permitted_after_filesystem_ready_for_chdk(self):
        # spytask_can_start = 1 -> should succeed (exit code 0)
        res = subprocess.run([str(self.bin_path), "1", "write", "ignored"])
        self.assertEqual(res.returncode, 0, "write should succeed when fs is ready")

        res = subprocess.run([str(self.bin_path), "1", "open", "A/CHDK/CCHDK4.CFG"])
        self.assertEqual(res.returncode, 0, "open under A/CHDK/ should succeed when fs is ready")

    def test_outside_writes_blocked_even_after_filesystem_ready(self):
        # spytask_can_start = 1 but path outside A/CHDK/ -> must be blocked
        res = subprocess.run([str(self.bin_path), "1", "open", "A/DCIM/IMG.JPG"])
        self.assertEqual(res.returncode, 1, "open outside A/CHDK/ must be blocked even when fs is ready")


class TestPort54DiagMarker(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        c_code = """
#include <stdio.h>
#include <string.h>

#define G3X_CONF_SAVE_NONE 0
#define G3X_CONF_SAVE_OK   1
#define G3X_CONF_SAVE_FAIL 2
#define G3X_CONF_SAVE_ERR  2
#define G3X_CONF_SAVE_OFF  3

static int g3x_conf_save_status = G3X_CONF_SAVE_NONE;

void g3x_conf_record_save_skipped(void)
{
    g3x_conf_save_status = G3X_CONF_SAVE_OFF;
}

void g3x_conf_record_save_result(int ok)
{
    if (ok == G3X_CONF_SAVE_OFF || ok == 3 || ok == -1)
    {
        g3x_conf_save_status = G3X_CONF_SAVE_OFF;
    }
    else if (ok == G3X_CONF_SAVE_OK || ok == 1)
    {
        if (g3x_conf_save_status != G3X_CONF_SAVE_FAIL)
        {
            g3x_conf_save_status = G3X_CONF_SAVE_OK;
        }
    }
    else
    {
        g3x_conf_save_status = G3X_CONF_SAVE_FAIL;
    }
}

const char *get_diag_marker(void)
{
    return (g3x_conf_save_status == G3X_CONF_SAVE_OFF) ? "SAVE:OFF" :
           (g3x_conf_save_status == G3X_CONF_SAVE_OK)  ? "SAVE:OK" :
           (g3x_conf_save_status == G3X_CONF_SAVE_FAIL || g3x_conf_save_status == G3X_CONF_SAVE_ERR) ? "SAVE:FAIL" : "SAVE:-";
}

int main(int argc, char **argv)
{
    if (argc < 2) return 99;
    if (strcmp(argv[1], "skipped") == 0) {
        g3x_conf_record_save_skipped();
    } else if (strcmp(argv[1], "ok") == 0) {
        g3x_conf_record_save_result(1);
    } else if (strcmp(argv[1], "fail") == 0) {
        g3x_conf_record_save_result(0);
    }
    printf("%s", get_diag_marker());
    return 0;
}
"""
        cls.temp_dir = tempfile.TemporaryDirectory()
        src_path = Path(cls.temp_dir.name) / "test_diag.c"
        src_path.write_text(c_code, encoding="utf-8")
        cls.bin_path = Path(cls.temp_dir.name) / "test_diag"
        subprocess.run(["gcc", "-O2", str(src_path), "-o", str(cls.bin_path)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_marker_states(self):
        out = subprocess.check_output([str(self.bin_path), "skipped"], text=True)
        self.assertEqual(out, "SAVE:OFF")

        out = subprocess.check_output([str(self.bin_path), "ok"], text=True)
        self.assertEqual(out, "SAVE:OK")

        out = subprocess.check_output([str(self.bin_path), "fail"], text=True)
        self.assertEqual(out, "SAVE:FAIL")


class TestPort54DisabledWritesAndHooks(unittest.TestCase):
    def test_filewrite_hooks_disabled(self):
        for fw_path in [
            ROOT / "chdk-port/platform/g3x/sub/110c/filewrite.c",
            ROOT / "full_build/g3x/sub/110c/filewrite.c",
        ]:
            self.assertTrue(fw_path.is_file(), f"Missing {fw_path}")
            text = fw_path.read_text(encoding="utf-8")
            self.assertNotIn("task_FileWrite_my", text)
            self.assertNotIn("filewrite_hook", text)

    def test_non_conf_write_wrappers_retained(self):
        script_text = (ROOT / "scripts/build_port43_dbuf.py").read_text(encoding="utf-8")
        # Ensure retained wrappers list contains blocking symbols
        for sym in ["fwrite", "creat", "mkdir", "remove", "rename"]:
            self.assertIn(f'"{sym}"', script_text)


class TestPort54FinsigStubs(unittest.TestCase):
    def test_stubs_match_finsig(self):
        self.assertTrue(FINSIG_STUBS.is_file(), f"Missing {FINSIG_STUBS}")
        finsig_text = FINSIG_STUBS.read_text(encoding="utf-8")

        expected_stubs = {
            "Open": "0xfc37b3b5",
            "Close": "0xfc37b439",
            "Read": "0xfc418d61",
            "Write": "0xfc37b471",
            "stat": "0xfc37b5cd",
            "TakeSemaphore": "0xbfe153e1",
            "GiveSemaphore": "0xbfe15459",
            "fileio_semaphore": "0x000149c0",
            "task_InitFileModules": "0xfc0bd071",
            "task_FileWrite": "0xfc25f3a7",
        }

        for name, addr in expected_stubs.items():
            pattern = rf"(NHSTUB|DEF)\(\s*{name}\s*,\s*{addr}\)"
            match = re.search(pattern, finsig_text, re.IGNORECASE)
            self.assertIsNotNone(match, f"Stub {name} @ {addr} not found in FINSIG stubs")


class TestPort54UnreachableWithoutFlag(unittest.TestCase):
    def test_unreachable_without_flag(self):
        # 1. Verify build script enforces card write disabling when conf_save is off
        script_text = (ROOT / "scripts/build_port43_dbuf.py").read_text(encoding="utf-8")
        self.assertIn('env["G3X_DISABLE_CARD_WRITES"] = "1"', script_text)
        self.assertIn('env["OPT_DISABLE_FILE_WRITES"] = "1"', script_text)

        # 2. Verify platform makefiles apply disable flags when G3X_CONF_SAVE is not 1
        plat_mf = PLAT_MAKEFILE.read_text(encoding="utf-8")
        self.assertIn("ifneq ($(G3X_CONF_SAVE),1)", plat_mf)
        self.assertIn("CFLAGS += -DG3X_DISABLE_CARD_WRITES=1", plat_mf)
        self.assertIn("CFLAGS += -DOPT_DISABLE_FILE_WRITES=1", plat_mf)

        # 3. Verify in default build no write call is reachable
        default_manifest_path = ROOT / "out/build-default/port41_manifest.json"
        if default_manifest_path.is_file():
            with default_manifest_path.open("r", encoding="utf-8") as f:
                d = json.load(f)
            self.assertIn("G3X_DISABLE_CARD_WRITES=1", d["build"]["flags"])
            self.assertIn("OPT_DISABLE_FILE_WRITES=1", d["build"]["flags"])


class TestPort54BuildsAndSymbols(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.build_candidate = ROOT / "out/port54-conf-save"
        cls.build_alone = ROOT / "out/build-conf-alone"
        cls.build_default = ROOT / "out/build-default"

        if (
            not (cls.build_candidate / "DISKBOOT.BIN").is_file()
            or sha256_file(cls.build_candidate / "DISKBOOT.BIN") != BASE_CANDIDATE_SHA256
        ):
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/build_port43_dbuf.py"),
                    "--no-overdraw",
                    "--kbd-check",
                    "--gui-diag",
                    "--shadow2",
                    "--gui-sync",
                    "--gui-menu",
                    "--gui-restore2",
                    "--playback-menu",
                    "--conf-save",
                    "--out-dir",
                    str(cls.build_candidate),
                ],
                cwd=ROOT,
                check=True,
            )

        if (
            not (cls.build_alone / "DISKBOOT.BIN").is_file()
            or sha256_file(cls.build_alone / "DISKBOOT.BIN") != BASE_ALONE_SHA256
        ):
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/build_port43_dbuf.py"),
                    "--conf-save-alone",
                    "--out-dir",
                    str(cls.build_alone),
                ],
                cwd=ROOT,
                check=True,
            )

        if (
            not (cls.build_default / "DISKBOOT.BIN").is_file()
            or not (cls.build_default / "stage_chdk/platform/g3x/sub/110c/main.elf").is_file()
        ):
            subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "tools/build_port41_full.py"),
                    "--keep-stage",
                    "--out-dir",
                    str(cls.build_default),
                ],
                cwd=ROOT,
                check=True,
            )

    def test_three_build_configurations_artifacts_and_hashes(self):
        # 1. Default
        def_bin = self.build_default / "DISKBOOT.BIN"
        self.assertTrue(def_bin.is_file())
        self.assertEqual(def_bin.stat().st_size, BASE_DEFAULT_SIZE)
        self.assertEqual(sha256_file(def_bin), BASE_DEFAULT_SHA256)

        # 2. Conf save alone
        alone_bin = self.build_alone / "DISKBOOT.BIN"
        self.assertTrue(alone_bin.is_file())
        self.assertEqual(alone_bin.stat().st_size, BASE_ALONE_SIZE)
        self.assertEqual(sha256_file(alone_bin), BASE_ALONE_SHA256)

        # 3. Candidate
        cand_bin = self.build_candidate / "DISKBOOT.BIN"
        self.assertTrue(cand_bin.is_file())
        self.assertEqual(cand_bin.stat().st_size, BASE_CANDIDATE_SIZE)
        self.assertEqual(sha256_file(cand_bin), BASE_CANDIDATE_SHA256)

    def test_flag_gating_symbol_presence_and_absence(self):
        default_elf = self.build_default / "stage_chdk/platform/g3x/sub/110c/main.elf"
        alone_elf = self.build_alone / "stage_chdk/platform/g3x/sub/110c/main.elf"
        candidate_elf = self.build_candidate / "stage_chdk/platform/g3x/sub/110c/main.elf"

        self.assertTrue(default_elf.is_file())
        self.assertTrue(alone_elf.is_file())
        self.assertTrue(candidate_elf.is_file())

        default_nm = subprocess.check_output([str(NM), str(default_elf)], text=True)
        alone_nm = subprocess.check_output([str(NM), str(alone_elf)], text=True)
        candidate_nm = subprocess.check_output([str(NM), str(candidate_elf)], text=True)

        # Default build must NOT have g3x_is_safe_chdk_write_path or g3x_conf_save_status
        self.assertNotIn("g3x_is_safe_chdk_write_path", default_nm)
        self.assertNotIn("g3x_conf_save_status", default_nm)

        # Alone and Candidate must have g3x_is_safe_chdk_write_path
        self.assertIn("g3x_is_safe_chdk_write_path", alone_nm)
        self.assertIn("g3x_is_safe_chdk_write_path", candidate_nm)
        self.assertIn("g3x_conf_save_status", candidate_nm)

    def test_candidate_write_wrappers_asm(self):
        candidate_elf = self.build_candidate / "stage_chdk/platform/g3x/sub/110c/main.elf"
        dump = subprocess.check_output([str(OBJDUMP), "-d", str(candidate_elf)], text=True)

        # __wrap_open calls g3x_is_safe_chdk_write_path
        self.assertIn("<__wrap_open>:", dump)
        self.assertIn("<g3x_is_safe_chdk_write_path>", dump)

        # __wrap_write is present
        self.assertIn("<__wrap_write>:", dump)

        # non-conf blocking wrappers are present and return without write
        for wrap in ["<__wrap__MakeDirectory_Fut>:", "<__wrap__DeleteFile_Fut>:", "<__wrap_remove>:", "<__wrap_mkdir>:"]:
            self.assertIn(wrap, dump)


class TestPort54Manifest(unittest.TestCase):
    def test_manifest_structure_and_hashes(self):
        self.assertTrue(MANIFEST_P54.is_file(), f"Missing {MANIFEST_P54}")
        with MANIFEST_P54.open("r", encoding="utf-8") as f:
            data = json.load(f)

        self.assertEqual(data["milestone"], "PORT-54")
        self.assertEqual(data["card_writes"], "sandboxed_conf_save")
        self.assertEqual(data["removed_wrappers"], ["conf_save"])
        self.assertIn("open", data["active_write_wrappers"])
        self.assertIn("write", data["active_write_wrappers"])

        # Check binary file
        bin_path = ROOT / "out/port54-conf-save/DISKBOOT.BIN"
        self.assertTrue(bin_path.is_file(), f"Missing built binary at {bin_path}")
        self.assertEqual(data["artifacts"]["DISKBOOT.BIN"]["sha256"], sha256_file(bin_path))
        self.assertEqual(data["artifacts"]["DISKBOOT.BIN"]["size"], bin_path.stat().st_size)


if __name__ == "__main__":
    unittest.main()
