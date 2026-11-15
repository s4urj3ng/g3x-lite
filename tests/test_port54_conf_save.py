"""Offline unit and integration tests for PORT-54 (G3X_CONF_SAVE=1).

Verifies:
1. Flag gating: G3X_CONF_SAVE=1 plumbing in makefiles and headers.
2. Default build byte-identity: Matches PORT-53 default SHA-256 and size.
3. Central path check: Real staged g3x_is_safe_chdk_write_path accepts A/CHDK/ paths and rejects outside paths, traversals ('..'), backslashes, and other drives.
4. Filesystem-ready gate: Real staged __wrap_write and __wrap_open refuse writes before spytask_can_start != 0.
5. Diag marker: Real gui_diag.h SAVE:OK on success, SAVE:FAIL on failure, SAVE:OFF when disabled; failure aggregated per-save and unlatched on next save.
6. Write restrictions: filewrite.c hooks, scripts, and logging remain disabled.
7. Stub verification: Platform stubs entry parsed and compared against reference/finsig_gm110c/stubs_entry.S and main.elf symbols.
8. Manifest verification: Candidate manifest contains expected artifacts, hashes, configurations, and wrappers.
9. Env-flag invocation: G3X_CONF_SAVE=1 alone builds cleanly without --conf-save-alone, conf_save unwrapped, no undefined symbols, and SAVE:OK/SAVE:FAIL present.
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
PLATFORM_STUBS_1 = ROOT / "chdk-port/platform/g3x/sub/110c/stubs_entry.S"
PLATFORM_STUBS_2 = ROOT / "chdk-port/platform/g3x/sub/110c/stubs_entry_2.S"
MANIFEST_P54 = ROOT / "manifests/port54_conf_save_manifest.json"

TOOLCHAIN_BIN = ROOT / "toolchains/gcc-arm-none-eabi-5_4-2016q3/bin"
NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"
OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"

BASE_DEFAULT_SHA256 = "24b8a024a216fe4db7d28b7aa97cf2410eaebf5cac9e7578a46f3b1e50004ae9"
BASE_DEFAULT_SIZE = 124097

BASE_ALONE_SHA256 = "8f3f3d4c21a0942420c8ea2894578a13d6f655bb5029da6321dfd480d397942e"
BASE_ALONE_SIZE = 124737

BASE_CANDIDATE_SHA256 = "452d942c586044e59c20ccc89dfd977c863c34c2ac33b8c103157cbd208f6be4"
BASE_CANDIDATE_SIZE = 133265


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def extract_staged_guard_source(lib_c_path: Path) -> str:
    text = lib_c_path.read_text(encoding="utf-8")
    start = text.index("volatile int g3x_conf_save_active = 0;")
    end = text.index("void *__wrap_fopen", start)
    return text[start:end]


def extract_staged_conf_save_source(conf_c_path: Path) -> str:
    text = conf_c_path.read_text(encoding="utf-8")
    start = text.index("static void config_update_last_saved(ConfInfo *ci)")
    end = text.index("int save_config_file(", start)
    return text[start:end]


def parse_asm_stubs(path: Path) -> dict[str, int]:
    text = path.read_text(encoding="utf-8")
    stubs: dict[str, int] = {}
    for m in re.finditer(r"(?:NHSTUB|DEF)\s*\(\s*([A-Za-z0-9_]+)\s*,\s*(0x[0-9a-fA-F]+)\)", text):
        stubs[m.group(1)] = int(m.group(2), 16)
    return stubs


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
        self.assertIn("g3x_conf_save_start", text)
        self.assertIn("g3x_conf_record_save_result", text)
        self.assertIn("g3x_conf_record_save_skipped", text)
        self.assertIn("g3x_conf_save_get_diag_str", text)


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
    """Compiles the REAL shipped guard source extracted from staged lib.c against mocked firmware calls."""

    @classmethod
    def setUpClass(cls):
        stage_lib = ROOT / "out/port54-conf-save/stage_chdk/platform/g3x/lib.c"
        if not stage_lib.is_file():
            # Build candidate to ensure stage is populated
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
                    str(ROOT / "out/port54-conf-save"),
                ],
                cwd=ROOT,
                check=True,
            )

        guard_code = extract_staged_guard_source(stage_lib)

        harness_code = f"""
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

volatile int spytask_can_start = 1;
static int mock_real_open_calls = 0;
static int mock_real_write_calls = 0;

int __real_open(const char *name, int flags, int mode)
{{
    (void)name; (void)flags; (void)mode;
    mock_real_open_calls++;
    return 42;
}}

int __real_write(int fd, const void *buf, int n)
{{
    (void)fd; (void)buf;
    mock_real_write_calls++;
    return n;
}}

/* Real guard source code extracted from staged lib.c */
{guard_code}

int main(int argc, char **argv)
{{
    if (argc < 2) return 2;
    const char *arg = argv[1];
    if (strcmp(arg, "__NULL__") == 0) {{
        return g3x_is_safe_chdk_write_path(NULL) ? 0 : 1;
    }}
    return g3x_is_safe_chdk_write_path(arg) ? 0 : 1;
}}
"""
        cls.temp_dir = tempfile.TemporaryDirectory()
        src_path = Path(cls.temp_dir.name) / "test_path.c"
        src_path.write_text(harness_code, encoding="utf-8")
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
    """Compiles the REAL shipped guard source to prove no write call is reachable before the filesystem-ready gate."""

    @classmethod
    def setUpClass(cls):
        stage_lib = ROOT / "out/port54-conf-save/stage_chdk/platform/g3x/lib.c"
        guard_code = extract_staged_guard_source(stage_lib)

        harness_code = f"""
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

volatile int spytask_can_start = 0;
static int mock_real_write_calls = 0;
static int mock_real_open_calls = 0;

int __real_write(int fd, const void *buf, int n)
{{
    (void)fd; (void)buf;
    mock_real_write_calls++;
    return n;
}}

int __real_open(const char *name, int flags, int mode)
{{
    (void)name; (void)flags; (void)mode;
    mock_real_open_calls++;
    return 42; // mock fd
}}

/* Real guard source code extracted from staged lib.c */
{guard_code}

int main(int argc, char **argv)
{{
    if (argc < 4) return 99;
    spytask_can_start = argv[1][0] - '0';
    g3x_conf_save_active = 1;
    int is_write = strcmp(argv[2], "write") == 0;
    const char *path = argv[3];

    mock_real_write_calls = 0;
    mock_real_open_calls = 0;

    if (is_write) {{
        int res = __wrap_write(1, "test", 4);
        return (res == 4 && mock_real_write_calls == 1) ? 0 : 1;
    }} else {{
        int res = __wrap_open(path, 0x0201 /* O_WRONLY|O_CREAT */, 0666);
        return (res == 42 && mock_real_open_calls == 1) ? 0 : 1;
    }}
}}
"""
        cls.temp_dir = tempfile.TemporaryDirectory()
        src_path = Path(cls.temp_dir.name) / "test_gate.c"
        src_path.write_text(harness_code, encoding="utf-8")
        cls.bin_path = Path(cls.temp_dir.name) / "test_gate"
        subprocess.run(["gcc", "-O2", str(src_path), "-o", str(cls.bin_path)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_writes_blocked_before_filesystem_ready(self):
        # spytask_can_start = 0 -> must return 1 (write/open refused, real call = 0)
        res = subprocess.run([str(self.bin_path), "0", "write", "ignored"])
        self.assertEqual(res.returncode, 1, "write should be blocked before fs ready")

        res = subprocess.run([str(self.bin_path), "0", "open", "A/CHDK/CCHDK4.CFG"])
        self.assertEqual(res.returncode, 1, "open for write should be blocked before fs ready")

    def test_writes_permitted_after_filesystem_ready_for_chdk(self):
        # spytask_can_start = 1 -> should succeed
        res = subprocess.run([str(self.bin_path), "1", "write", "ignored"])
        self.assertEqual(res.returncode, 0, "write should succeed when fs is ready")

        res = subprocess.run([str(self.bin_path), "1", "open", "A/CHDK/CCHDK4.CFG"])
        self.assertEqual(res.returncode, 0, "open under A/CHDK/ should succeed when fs is ready")

    def test_outside_writes_blocked_even_after_filesystem_ready(self):
        # spytask_can_start = 1 but path outside A/CHDK/ -> must be blocked
        res = subprocess.run([str(self.bin_path), "1", "open", "A/DCIM/IMG.JPG"])
        self.assertEqual(res.returncode, 1, "open outside A/CHDK/ must be blocked even when fs is ready")


class TestPort54SettingsSaveScopedPermission(unittest.TestCase):
    """Verifies that write permissions are scoped strictly to settings save operations,
    and validates mutation testing on the real guard source."""

    @classmethod
    def setUpClass(cls):
        stage_lib = ROOT / "out/port54-conf-save/stage_chdk/platform/g3x/lib.c"
        cls.guard_code = extract_staged_guard_source(stage_lib)

        def make_harness(src: str) -> str:
            return f"""
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

volatile int spytask_can_start = 1;
static int mock_real_write_calls = 0;
static int mock_real_open_calls = 0;

int __real_write(int fd, const void *buf, int n)
{{
    (void)fd; (void)buf;
    mock_real_write_calls++;
    return n;
}}

int __real_open(const char *name, int flags, int mode)
{{
    (void)name; (void)flags; (void)mode;
    mock_real_open_calls++;
    return 42;
}}

{src}

int main(int argc, char **argv)
{{
    if (argc < 3) return 99;
    const char *cmd = argv[1];
    const char *arg = argv[2];

    mock_real_write_calls = 0;
    mock_real_open_calls = 0;

    if (strcmp(cmd, "open_inactive") == 0) {{
        g3x_conf_save_active = 0;
        int fd = __wrap_open(arg, 0x0201, 0666);
        return (fd < 0 && mock_real_open_calls == 0) ? 0 : 1;
    }}
    if (strcmp(cmd, "write_inactive") == 0) {{
        g3x_conf_save_active = 0;
        int wb = __wrap_write(1, "data", 4);
        return (wb < 0 && mock_real_write_calls == 0) ? 0 : 1;
    }}
    if (strcmp(cmd, "open_active") == 0) {{
        g3x_conf_save_active = 1;
        int fd = __wrap_open(arg, 0x0201, 0666);
        return (fd == 42 && mock_real_open_calls == 1) ? 0 : 1;
    }}
    if (strcmp(cmd, "write_active") == 0) {{
        g3x_conf_save_active = 1;
        int wb = __wrap_write(1, "data", 4);
        return (wb == 4 && mock_real_write_calls == 1) ? 0 : 1;
    }}
    return 99;
}}
"""
        cls.temp_dir = tempfile.TemporaryDirectory()

        # Real harness
        src_path = Path(cls.temp_dir.name) / "test_scope.c"
        src_path.write_text(make_harness(cls.guard_code), encoding="utf-8")
        cls.bin_path = Path(cls.temp_dir.name) / "test_scope"
        subprocess.run(["gcc", "-O2", str(src_path), "-o", str(cls.bin_path)], check=True)

        # Mutated harness: guard stubbed out in __wrap_open
        mutated_code = cls.guard_code.replace(
            "if ((flags & 3) != 0 || (flags & (0x08 | 0x0100 | 0x0200 | 0x0400 | 0x0800)))",
            "if (0 && (flags & 3) != 0)"
        )
        mut_path = Path(cls.temp_dir.name) / "test_mutated.c"
        mut_path.write_text(make_harness(mutated_code), encoding="utf-8")
        cls.mut_bin_path = Path(cls.temp_dir.name) / "test_mutated"
        subprocess.run(["gcc", "-O2", str(mut_path), "-o", str(cls.mut_bin_path)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_outside_conf_save_scope_rejected(self):
        # All writes rejected when g3x_conf_save_active == 0
        outside_paths = [
            "A/CHDK/LOGS/LOG_0001.TXT",
            "A/CHDK/CCHDK4.CFG",
            "A/CHDK/OSD__4.CFG",
            "A/CHDK/UMENU4.CFG",
            "A/CHDK/GPS__4.CFG",
            "A/CHDK/test.cfg",
        ]
        for p in outside_paths:
            res = subprocess.run([str(self.bin_path), "open_inactive", p])
            self.assertEqual(res.returncode, 0, f"open outside scope should reject '{p}'")

        res = subprocess.run([str(self.bin_path), "write_inactive", "dummy"])
        self.assertEqual(res.returncode, 0, "write outside scope should be rejected")

    def test_conf_file_inside_scope_accepted(self):
        # Conf files accepted when g3x_conf_save_active == 1
        conf_paths = [
            "A/CHDK/CCHDK4.CFG",
            "a/chdk/cchdk4.cfg",
            "A/CHDK/OSD__4.CFG",
            "a/chdk/osd__4.cfg",
            "A/CHDK/UMENU4.CFG",
            "a/chdk/umenu4.cfg",
            "A/CHDK/GPS__4.CFG",
            "a/chdk/gps__4.cfg",
            "A:/CHDK/CCHDK4.CFG",
            "a:/chdk/cchdk4.cfg",
        ]
        for p in conf_paths:
            res = subprocess.run([str(self.bin_path), "open_active", p])
            self.assertEqual(res.returncode, 0, f"conf file inside scope '{p}' should be accepted")

        res = subprocess.run([str(self.bin_path), "write_active", "dummy"])
        self.assertEqual(res.returncode, 0, "write inside scope should succeed")

    def test_non_conf_paths_inside_scope_rejected(self):
        # Non-conf paths refused even when g3x_conf_save_active == 1
        non_conf = [
            "A/CHDK/LOGS/LOG_0001.TXT",
            "A/CHDK/SCRIPTS/test.lua",
            "A/CHDK/FONTS/font.rbf",
            "A/CHDK/MODULES/module.flt",
            "A/DCIM/100CANON/IMG_0001.JPG",
            "../A/CHDK/CCHDK4.CFG",
            "B/CHDK/CCHDK4.CFG",
            "A\\CHDK\\CCHDK4.CFG",
        ]
        for p in non_conf:
            res = subprocess.run([str(self.bin_path), "open_active", p])
            self.assertEqual(res.returncode, 1, f"non-conf path '{p}' inside scope must be rejected")

    def test_mutation_guard_removal_fails(self):
        # With real guard: writing to A/DCIM/100CANON/IMG_0001.JPG is rejected (exit code 1)
        res_real = subprocess.run([str(self.bin_path), "open_active", "A/DCIM/100CANON/IMG_0001.JPG"])
        self.assertEqual(res_real.returncode, 1, "Real guard must refuse write to outside path")

        # With mutated guard (guard removed/stubbed): write is mistakenly permitted (exit code 0)
        res_mut = subprocess.run([str(self.mut_bin_path), "open_active", "A/DCIM/100CANON/IMG_0001.JPG"])
        self.assertEqual(res_mut.returncode, 0, "Mutated guard without path check erroneously permits outside write")


class TestPort54DiagMarker(unittest.TestCase):
    """Compiles the REAL shipped gui_diag.h to verify:
    1. SAVE:OFF, SAVE:OK, SAVE:FAIL marker states
    2. Failure aggregation across files within one save operation
    3. Unlatching: a failed save followed by a successful save shows SAVE:OK
    """

    @classmethod
    def setUpClass(cls):
        c_code = f"""
#include <stdio.h>
#include <string.h>
#include <stdlib.h>

#define G3X_CONF_SAVE 1
#define G3X_GUI_DIAG_IMPLEMENTATION 1
#include "{DIAG_HEADER}"

int main(int argc, char **argv)
{{
    if (argc < 2) return 99;
    const char *cmd = argv[1];

    if (strcmp(cmd, "skipped") == 0) {{
        g3x_conf_record_save_skipped();
        printf("%s", g3x_conf_save_get_diag_str());
        return 0;
    }}
    if (strcmp(cmd, "ok") == 0) {{
        g3x_conf_save_start();
        g3x_conf_record_save_result(1);
        printf("%s", g3x_conf_save_get_diag_str());
        return 0;
    }}
    if (strcmp(cmd, "fail") == 0) {{
        g3x_conf_save_start();
        g3x_conf_record_save_result(2);
        printf("%s", g3x_conf_save_get_diag_str());
        return 0;
    }}
    if (strcmp(cmd, "aggregate_fail") == 0) {{
        // Inside one save operation: file 1 ok, file 2 fail, file 3 ok -> FAIL
        g3x_conf_save_start();
        g3x_conf_record_save_result(1);
        g3x_conf_record_save_result(2);
        g3x_conf_record_save_result(1);
        printf("%s", g3x_conf_save_get_diag_str());
        return 0;
    }}
    if (strcmp(cmd, "unlatched_recovery") == 0) {{
        // Save 1 fails
        g3x_conf_save_start();
        g3x_conf_record_save_result(2);
        if (strcmp(g3x_conf_save_get_diag_str(), "SAVE:FAIL") != 0) return 1;

        // Save 2 starts and succeeds
        g3x_conf_save_start();
        g3x_conf_record_save_result(1);
        g3x_conf_record_save_result(1);
        printf("%s", g3x_conf_save_get_diag_str());
        return 0;
    }}
    return 99;
}}
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

    def test_failure_aggregation_across_files_within_one_save(self):
        out = subprocess.check_output([str(self.bin_path), "aggregate_fail"], text=True)
        self.assertEqual(out, "SAVE:FAIL", "A failure on any file in an operation must latch SAVE:FAIL for that operation")

    def test_failed_save_followed_by_successful_save_shows_save_ok(self):
        out = subprocess.check_output([str(self.bin_path), "unlatched_recovery"], text=True)
        self.assertEqual(out, "SAVE:OK", "Reset at the start of each conf_save operation must allow recovery to SAVE:OK")


class TestPort54RetryOnFailure(unittest.TestCase):
    """Compiles the REAL staged conf_save and config_save source to verify:
    1. Open failure: does not update last_saved, latches SAVE:FAIL; next conf_save retries and succeeds (SAVE:OK).
    2. Short write: does not update last_saved, latches SAVE:FAIL; next conf_save retries and succeeds (SAVE:OK).
    3. Persistent failure: both calls report SAVE:FAIL and the retry still attempts a write.
    4. Mutation check: unconditional config_update_last_saved() causes the retry to be skipped.
    """

    @classmethod
    def setUpClass(cls):
        stage_conf = ROOT / "out/port54-conf-save/stage_chdk/core/conf.c"
        if not stage_conf.is_file():
            # Build candidate to ensure stage is populated
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
                    str(ROOT / "out/port54-conf-save"),
                ],
                cwd=ROOT,
                check=True,
            )

        cls.conf_code = extract_staged_conf_save_source(stage_conf)

        def make_harness(src_block: str) -> str:
            return f"""
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdint.h>
#include <fcntl.h>

#define G3X_CONF_SAVE 1
#define G3X_GUI_DIAG_IMPLEMENTATION 1
#include "{DIAG_HEADER}"

volatile int g3x_conf_save_active = 0;

#define CONF_MAGICK_VALUE 0x4B444843
#define CONF_DEF_VALUE 1
#define CONF_OSD_POS 2
#define CONF_FUNC_PTR 3
#define CONF_INT_PTR 4
#define CONF_CHAR_PTR 5
#define CONF_STRUCT_PTR 8
#define CONF_STR_LEN 30
#define CONF_USER 3000

typedef struct {{
    unsigned short id;
    unsigned char size;
    char type;
    void *var;
    union {{
        void *ptr;
        int i;
        long (*func)(void);
    }};
    unsigned int last_saved;
}} ConfInfo;

typedef struct {{
    int num_items;
    int item_size;
    int (*saved_size)();
    char* (*save)(char *dst);
    int (*load)(char *src);
}} tVarArrayConfig;

typedef struct {{
    int start_id, end_id;
    ConfInfo *ci;
    char *filename;
    void (*info_func)(unsigned short id);
}} confinfo_handler;

static const confinfo_handler confinfo_handlers[];

struct {{
    struct {{
        int user_menu_has_changed;
    }} state;
}} camera_info;

static unsigned int memhash31(unsigned char *buf, int len) {{ (void)buf; (void)len; return 0; }}
static unsigned int lang_strhash31(intptr_t id) {{ (void)id; return 0; }}
static void* umalloc(size_t s) {{ return malloc(s); }}
static void ufree(void *p) {{ free(p); }}
static void user_menu_save(void) {{}}
static void save_params_values(int enforce) {{ (void)enforce; }}

static int mock_open_ret = 10;
static int mock_open_calls = 0;
static int mock_write_mode = 0; // 0: full, 1: short write, 2: fail
static int mock_write_calls = 0;
static int mock_close_ret = 0;
static int mock_close_calls = 0;

int open(const char *name, int flags, ...)
{{
    (void)name; (void)flags;
    mock_open_calls++;
    return mock_open_ret;
}}

ssize_t write(int fd, const void *buf, size_t count)
{{
    (void)fd; (void)buf;
    mock_write_calls++;
    if (mock_write_mode == 1) return count > 1 ? count - 1 : 0; // short write
    if (mock_write_mode == 2) return -1;
    return count;
}}

int close(int fd)
{{
    (void)fd;
    mock_close_calls++;
    return mock_close_ret;
}}

/* Real staged code */
{src_block}

static int setting1 = 100;
static ConfInfo test_ci[] = {{
    {{ 1, sizeof(int), CONF_DEF_VALUE, &setting1, {{ .i = 0 }}, 0 }},
    {{ 0, 0, 0, NULL, {{ .i = 0 }}, 0 }}
}};

static const confinfo_handler confinfo_handlers[] = {{
    {{ 1, 999, test_ci, "A/CHDK/CCHDK4.CFG", NULL }},
    {{ 0, 0, NULL, NULL, NULL }}
}};

int main(int argc, char **argv)
{{
    if (argc < 2) return 99;
    const char *test = argv[1];

    if (strcmp(test, "open_fail_then_retry") == 0) {{
        setting1 = 100;
        test_ci[0].last_saved = 0; // changed

        // Step 1: Open fails
        mock_open_ret = -1;
        mock_open_calls = 0;
        mock_write_calls = 0;
        conf_save();

        if (mock_open_calls != 1) return 1;
        if (mock_write_calls != 0) return 2;
        if (test_ci[0].last_saved != 0) return 3; // must NOT update last_saved
        if (strcmp(g3x_conf_save_get_diag_str(), "SAVE:FAIL") != 0) return 4;

        // Step 2: Retry with working mock (no edits made)
        mock_open_ret = 10;
        mock_write_mode = 0;
        mock_open_calls = 0;
        mock_write_calls = 0;
        conf_save();

        if (mock_open_calls != 1) return 5; // must attempt retry
        if (mock_write_calls != 1) return 6;
        if (test_ci[0].last_saved != 100) return 7; // now updated
        if (strcmp(g3x_conf_save_get_diag_str(), "SAVE:OK") != 0) return 8;

        // Step 3: No edits -> no write call reachable, remains SAVE:OK
        mock_open_calls = 0;
        mock_write_calls = 0;
        conf_save();
        if (mock_open_calls != 0) return 9;
        if (strcmp(g3x_conf_save_get_diag_str(), "SAVE:OK") != 0) return 10;

        return 0;
    }}

    if (strcmp(test, "short_write_then_retry") == 0) {{
        setting1 = 200;
        test_ci[0].last_saved = 0; // changed

        // Step 1: Short write
        mock_open_ret = 10;
        mock_write_mode = 1; // short write
        mock_open_calls = 0;
        mock_write_calls = 0;
        conf_save();

        if (mock_open_calls != 1) return 21;
        if (mock_write_calls != 1) return 22;
        if (test_ci[0].last_saved != 0) return 23; // must NOT update last_saved
        if (strcmp(g3x_conf_save_get_diag_str(), "SAVE:FAIL") != 0) return 24;

        // Step 2: Retry with working mock
        mock_write_mode = 0;
        mock_open_calls = 0;
        mock_write_calls = 0;
        conf_save();

        if (mock_open_calls != 1) return 25; // must retry
        if (mock_write_calls != 1) return 26;
        if (test_ci[0].last_saved != 200) return 27; // now updated
        if (strcmp(g3x_conf_save_get_diag_str(), "SAVE:OK") != 0) return 28;

        return 0;
    }}

    if (strcmp(test, "persistent_failure") == 0) {{
        setting1 = 300;
        test_ci[0].last_saved = 0;

        // Call 1: fails
        mock_open_ret = -1;
        mock_open_calls = 0;
        conf_save();
        if (mock_open_calls != 1) return 31;
        if (test_ci[0].last_saved != 0) return 32;
        if (strcmp(g3x_conf_save_get_diag_str(), "SAVE:FAIL") != 0) return 33;

        // Call 2: still failing
        mock_open_calls = 0;
        conf_save();
        if (mock_open_calls != 1) return 34; // still attempts write
        if (test_ci[0].last_saved != 0) return 35;
        if (strcmp(g3x_conf_save_get_diag_str(), "SAVE:FAIL") != 0) return 36;

        return 0;
    }}

    return 99;
}}
"""
        cls.temp_dir = tempfile.TemporaryDirectory()

        # Compile real harness
        src_path = Path(cls.temp_dir.name) / "test_retry.c"
        src_path.write_text(make_harness(cls.conf_code), encoding="utf-8")
        cls.bin_path = Path(cls.temp_dir.name) / "test_retry"
        subprocess.run(["gcc", "-Wno-pointer-to-int-cast", "-O2", str(src_path), "-o", str(cls.bin_path)], check=True)

        # Compile mutated harness (unconditional config_update_last_saved restored)
        mut_code = cls.conf_code.replace(
            "if (config_save(confinfo_handlers[i].ci, confinfo_handlers[i].filename, confinfo_handlers[i].start_id)) {\n                config_update_last_saved(confinfo_handlers[i].ci);\n            }",
            "config_save(confinfo_handlers[i].ci, confinfo_handlers[i].filename, confinfo_handlers[i].start_id);\n            config_update_last_saved(confinfo_handlers[i].ci);"
        )
        mut_path = Path(cls.temp_dir.name) / "test_mutated_retry.c"
        mut_path.write_text(make_harness(mut_code), encoding="utf-8")
        cls.mut_bin_path = Path(cls.temp_dir.name) / "test_mutated_retry"
        subprocess.run(["gcc", "-Wno-pointer-to-int-cast", "-O2", str(mut_path), "-o", str(cls.mut_bin_path)], check=True)

    @classmethod
    def tearDownClass(cls):
        cls.temp_dir.cleanup()

    def test_open_failure_then_retry_with_working_mock_succeeds_and_updates_last_saved(self):
        res = subprocess.run([str(self.bin_path), "open_fail_then_retry"])
        self.assertEqual(res.returncode, 0, "Open failure followed by retry must attempt write again and succeed with SAVE:OK")

    def test_short_write_then_retry_with_working_mock_succeeds(self):
        res = subprocess.run([str(self.bin_path), "short_write_then_retry"])
        self.assertEqual(res.returncode, 0, "Short write failure followed by retry must attempt write again and succeed with SAVE:OK")

    def test_persistent_failure_both_calls_report_fail_and_retry_attempts_write(self):
        res = subprocess.run([str(self.bin_path), "persistent_failure"])
        self.assertEqual(res.returncode, 0, "Persistent failure must keep reporting SAVE:FAIL and retry must still attempt write")

    def test_mutation_check_unconditional_update_fails_retry(self):
        # With mutated source (unconditional config_update_last_saved restored),
        # last_saved is incorrectly updated on failure, so retry does NOT attempt write.
        # This test verifies that the mutated code fails the open_fail_then_retry contract.
        res = subprocess.run([str(self.mut_bin_path), "open_fail_then_retry"])
        self.assertNotEqual(res.returncode, 0, "Unconditional config_update_last_saved must fail the retry contract")


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
        for sym in ["fwrite", "creat", "mkdir", "remove", "rename"]:
            self.assertIn(f'"{sym}"', script_text)


class TestPort54FinsigStubs(unittest.TestCase):
    """Parses platform stubs actually used by the build (stubs_entry*.S and main.elf)
    and verifies each one matches reference/finsig_gm110c/stubs_entry.S."""

    def test_stubs_match_finsig(self):
        self.assertTrue(FINSIG_STUBS.is_file(), f"Missing {FINSIG_STUBS}")
        self.assertTrue(PLATFORM_STUBS_1.is_file(), f"Missing {PLATFORM_STUBS_1}")
        self.assertTrue(PLATFORM_STUBS_2.is_file(), f"Missing {PLATFORM_STUBS_2}")

        finsig_stubs = parse_asm_stubs(FINSIG_STUBS)
        platform_stubs = parse_asm_stubs(PLATFORM_STUBS_1)
        platform_stubs.update(parse_asm_stubs(PLATFORM_STUBS_2))

        required_symbols = [
            "Open",
            "Close",
            "Read",
            "Write",
            "stat",
            "fileio_semaphore",
            "TakeSemaphore",
            "GiveSemaphore",
            "task_InitFileModules",
            "task_FileWrite",
        ]

        for name in required_symbols:
            self.assertIn(name, finsig_stubs, f"Stub {name} missing from FINSIG")
            self.assertIn(name, platform_stubs, f"Stub {name} missing from platform stubs")
            self.assertEqual(
                platform_stubs[name],
                finsig_stubs[name],
                f"Stub {name} address mismatch: platform={hex(platform_stubs[name])} finsig={hex(finsig_stubs[name])}",
            )

        # Cross-check absolute symbols against built main.elf symbol table
        candidate_elf = ROOT / "out/port54-conf-save/stage_chdk/platform/g3x/sub/110c/main.elf"
        self.assertTrue(candidate_elf.is_file(), f"Missing {candidate_elf}")
        nm_out = subprocess.check_output([str(NM), str(candidate_elf)], text=True)
        elf_symbols: dict[str, int] = {}
        for line in nm_out.splitlines():
            parts = line.split()
            if len(parts) == 3:
                addr, _, sym_name = parts
                elf_symbols[sym_name] = int(addr, 16)

        for abs_sym in ["fileio_semaphore", "task_InitFileModules", "task_FileWrite"]:
            self.assertIn(abs_sym, elf_symbols)
            self.assertEqual(elf_symbols[abs_sym], finsig_stubs[abs_sym])


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

        # Alone and Candidate must have g3x_is_safe_chdk_write_path and g3x_conf_save_status
        self.assertIn("g3x_is_safe_chdk_write_path", alone_nm)
        self.assertIn("g3x_conf_save_status", alone_nm)
        self.assertIn("g3x_is_safe_chdk_write_path", candidate_nm)
        self.assertIn("g3x_conf_save_status", candidate_nm)

    def test_candidate_write_wrappers_asm(self):
        candidate_elf = self.build_candidate / "stage_chdk/platform/g3x/sub/110c/main.elf"
        dump = subprocess.check_output([str(OBJDUMP), "-d", str(candidate_elf)], text=True)

        # __wrap_open calls g3x_is_safe_chdk_write_path and g3x_is_conf_file_path
        self.assertIn("<__wrap_open>:", dump)
        self.assertIn("<g3x_is_safe_chdk_write_path>", dump)
        self.assertIn("<g3x_is_conf_file_path>", dump)

        # __wrap_write is present
        self.assertIn("<__wrap_write>:", dump)

        # g3x_conf_save_active symbol is present
        nm_out = subprocess.check_output([str(NM), str(candidate_elf)], text=True)
        self.assertIn("g3x_conf_save_active", nm_out)

        # non-conf blocking wrappers are present and return without write
        for wrap in ["<__wrap__MakeDirectory_Fut>:", "<__wrap__DeleteFile_Fut>:", "<__wrap_remove>:", "<__wrap_mkdir>:"]:
            self.assertIn(wrap, dump)

    def test_env_flag_invocation_conf_save_only(self):
        """Tests the advertised env-flag invocation (G3X_CONF_SAVE=1 only, no --conf-save-alone).
        Verifies conf_save is unwrapped, no undefined g3x_conf_* symbols, and SAVE:OK/SAVE:FAIL present."""
        with tempfile.TemporaryDirectory() as td:
            out_dir = Path(td)
            env = os.environ.copy()
            env["G3X_CONF_SAVE"] = "1"
            for k in list(env.keys()):
                if k.startswith("G3X_") and k != "G3X_CONF_SAVE":
                    del env[k]

            res = subprocess.run(
                [
                    sys.executable,
                    "-B",
                    str(ROOT / "scripts/build_port43_dbuf.py"),
                    "--out-dir",
                    str(out_dir),
                ],
                cwd=ROOT,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res.returncode, 0, f"Env build failed: {res.stderr}")

            # 1. Verify conf_save is not wrapped in sub makefile
            sub_mf = out_dir / "stage_chdk/platform/g3x/sub/110c/Makefile"
            self.assertTrue(sub_mf.is_file())
            self.assertNotIn("-Wl,--wrap=conf_save", sub_mf.read_text(encoding="utf-8"))

            # 2. Verify no undefined g3x_conf_* symbols in main.elf
            main_elf = out_dir / "stage_chdk/platform/g3x/sub/110c/main.elf"
            self.assertTrue(main_elf.is_file())
            nm_u = subprocess.check_output([str(NM), "-u", str(main_elf)], text=True)
            undef_conf = [line for line in nm_u.splitlines() if "g3x_conf" in line]
            self.assertEqual(undef_conf, [], f"Found undefined g3x_conf symbols: {undef_conf}")

            # 3. Verify SAVE:OK and SAVE:FAIL strings are present in binary
            main_bin = out_dir / "stage_chdk/platform/g3x/sub/110c/main.bin"
            self.assertTrue(main_bin.is_file())
            strings_out = subprocess.check_output(["strings", str(main_bin)], text=True)
            self.assertIn("SAVE:OK", strings_out)
            self.assertIn("SAVE:FAIL", strings_out)


class TestPort54ConfSaveReachability(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.candidate_elf = ROOT / "out/port54-conf-save/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.default_elf = ROOT / "out/build-default/stage_chdk/platform/g3x/sub/110c/main.elf"
        cls.staged_conf_c = ROOT / "out/port54-conf-save/stage_chdk/core/conf.c"
        cls.gcc = TOOLCHAIN_BIN / "arm-none-eabi-gcc"
        cls.stage_dir = ROOT / "out/port54-conf-save/stage_chdk"

    def test_combined_candidate_disassembly_reaches_real_open_and_write(self):
        self.assertTrue(self.candidate_elf.is_file(), f"Missing {self.candidate_elf}")
        dump = subprocess.check_output([str(OBJDUMP), "-d", str(self.candidate_elf)], text=True)

        m = re.search(r"<config_save>:\s*\n((?:\s+[0-9a-f]+:.*\n)+)", dump)
        self.assertIsNotNone(m, "config_save symbol not found in candidate disassembly")
        config_save_asm = m.group(1)

        self.assertIn("<__wrap_open>", config_save_asm)
        self.assertIn("<__wrap_write>", config_save_asm)
        self.assertIn("<close>", config_save_asm)
        self.assertIn("<umalloc>", config_save_asm)

        m2 = re.search(r"<conf_save>:\s*\n((?:\s+[0-9a-f]+:.*\n)+)", dump)
        self.assertIsNotNone(m2, "conf_save symbol not found in candidate disassembly")
        conf_save_asm = m2.group(1)
        self.assertIn("<config_save>", conf_save_asm)
        self.assertIn("<config_has_changed>", conf_save_asm)

    def test_preprocessor_actual_staged_source_combined_vs_playback_without_conf_save(self):
        self.assertTrue(self.staged_conf_c.is_file(), f"Missing {self.staged_conf_c}")
        base_cmd = [
            str(self.gcc),
            "-E",
            "-nostdinc",
            f"-I{self.stage_dir}/include",
            f"-I{self.stage_dir}/core",
            f"-I{self.stage_dir}/modules",
            f"-I{self.stage_dir}/platform/g3x",
            f"-I{self.stage_dir}/platform/generic",
            "-DG3X_FULL_BUILD=1",
            "-DG3X_GUI_SHADOW2=1",
            "-DG3X_GUI_SYNC=1",
            "-DG3X_GUI_MENU=1",
            "-DG3X_GUI_RESTORE2=1",
            "-DG3X_PLAYBACK_MENU=1",
            "-DG3X_GUI_DIAG=1",
            "-DG3X_KBD_CHECK=1",
            "-DG3X_GUI_FIX=1",
            "-DG3X_GUI_DBUF=1",
            "-DG3X_GUI_NOOVERDRAW=1",
            "-DG3X_DISABLE_CARD_WRITES=1",
            "-DCAM_SUPPORT_BITMAP_RES_CHANGE=1",
            "-DOPT_DISABLE_FILE_WRITES=1",
        ]

        # 1. Combined configuration (+ G3X_CONF_SAVE=1)
        cmd_cand = base_cmd + ["-DG3X_CONF_SAVE=1", str(self.staged_conf_c)]
        out_cand = subprocess.check_output(cmd_cand, text=True)
        m_cand = re.search(r"(?:void|int)\s+config_save\([^)]*\)\s*\{(.*?)\n\}", out_cand, re.DOTALL)
        self.assertIsNotNone(m_cand, "config_save not found in preprocessed candidate output")
        cfg_cand_body = m_cand.group(1)
        self.assertIn("open(filename,", cfg_cand_body)
        self.assertIn("write(fd,", cfg_cand_body)
        self.assertIn("g3x_conf_save_active = 1;", cfg_cand_body)
        self.assertIn("g3x_conf_save_active = 0;", cfg_cand_body)
        self.assertNotIn("g3x_conf_record_save_result(3", cfg_cand_body)

        # 2. PLAYBACK_MENU-without-CONF_SAVE (no G3X_CONF_SAVE)
        cmd_p53 = base_cmd + [str(self.staged_conf_c)]
        out_p53 = subprocess.check_output(cmd_p53, text=True)
        m_p53 = re.search(r"(?:void|int)\s+config_save\([^)]*\)\s*\{(.*?)\n\}", out_p53, re.DOTALL)
        self.assertIsNotNone(m_p53, "config_save not found in preprocessed PORT-53 output")
        cfg_p53_body = m_p53.group(1)
        self.assertIn("g3x_conf_record_save_result(3", cfg_p53_body)
        self.assertNotIn("open(filename,", cfg_p53_body)
        self.assertNotIn("write(fd,", cfg_p53_body)

    def test_default_build_conf_save_unreachable(self):
        self.assertTrue(self.default_elf.is_file(), f"Missing {self.default_elf}")
        dump = subprocess.check_output([str(OBJDUMP), "-d", str(self.default_elf)], text=True)

        self.assertIn("<__wrap_conf_save>:", dump)
        m = re.search(r"<__wrap_conf_save>:\s*\n\s*[0-9a-f]+:\s+4770\s+bx\s+lr", dump)
        self.assertIsNotNone(m, "__wrap_conf_save must be an empty bx lr stub in default build")

        self.assertIn("<__wrap_open>:", dump)
        self.assertNotIn("<g3x_is_safe_chdk_write_path>", dump)


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

        # Check all three configurations recorded in manifest
        self.assertIn("configurations", data)
        configs = data["configurations"]
        for c in ["default", "conf_save_alone", "full_candidate"]:
            self.assertIn(c, configs)
            c_bin = ROOT / configs[c]["path"]
            self.assertTrue(c_bin.is_file(), f"Missing configuration binary at {c_bin}")
            self.assertEqual(configs[c]["sha256"], sha256_file(c_bin))
            self.assertEqual(configs[c]["size"], c_bin.stat().st_size)


if __name__ == "__main__":
    unittest.main()
