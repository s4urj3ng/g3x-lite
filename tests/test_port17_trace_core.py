#!/usr/bin/env python3
"""Unit tests for PORT-17 compile-time trace core.

Verifies:
1. Compile-time flags default to OFF (G3X_TRACE=0, G3X_TRACE_FLUSH=0, G3X_TRACE_LED=0).
2. Magic signature is 0x43415254 (ASCII 'TRAC' in memory order: 'T','R','A','C').
   Packed with struct '<I', raw bytes at offsets 0..3 are exactly b"TRAC".
3. Record, header, and ring layout constants are consistent and documented.
4. C struct byte sizes, field offsets, and Little-Endian format match the specification.
5. Stage-marker macros exist for entry, relocation, task hooks, kbd, display, and assert,
   and expand to nothing when tracing is OFF.
6. Trace flush routine to A/CHDK/LOGS/TRACE.LOG is behind G3X_TRACE_FLUSH and hits
   a compile-time #error naming Q-P17-04, Q-P17-05, Q-P17-07, and Q-P17-11 when enabled.
7. LED blink fallback is behind G3X_TRACE_LED and hits a compile-time #error
   naming Q-P17-03, Q-P17-06, Q-P17-08, and Q-P17-09 when enabled.
8. Firmware-independent pure logic helpers (log size cap check, serialization,
   blink pattern) work correctly.
9. No uncited firmware RAM addresses are present and stubs_prototype.S is unchanged.
10. Candidate build and validator pass with tracing OFF, preserving PORT-16
    layout invariant addresses: _start=0x003489B4, boot_witness=0x0035F7A0, _end=0x00366CB0.
11. Pinned ARM toolchain links prototype with -DG3X_TRACE=1:
    - g3x_trace_ring is in .bss
    - g3x_trace_ring is 16-byte aligned
    - g3x_trace_ring sits after boot_witness
    - g3x_trace_init/g3x_trace_record are linked in
    - boot_witness does not move below 0x0035F7A0 (ON layout is pinned later)
    - _end grows by at least ALIGN_UP(sizeof ring, 16)
12. With the candidate CFLAGS (LOW_LEVEL) and the pinned toolchain:
    - G3X_TRACE=1: g3x_trace.o defines g3x_trace_init/g3x_trace_record and the
      markers expand to g3x_trace_record calls
    - G3X_TRACE=0 or unset: markers expand to ((void)0) and g3x_trace.o is empty
13. boot_prototype.c is byte-identical and g3x_trace.c is not wired into the builder.
"""

import hashlib
import os
import re
import struct
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TRACE_H_PATH = os.path.join(REPO_ROOT, "chdk-port", "platform", "g3x", "sub", "110c", "g3x_trace.h")
TRACE_C_PATH = os.path.join(REPO_ROOT, "chdk-port", "platform", "g3x", "sub", "110c", "g3x_trace.c")
BOOT_PROTO_PATH = os.path.join(REPO_ROOT, "chdk-port", "platform", "g3x", "sub", "110c", "boot_prototype.c")
STUBS_PROTO_PATH = os.path.join(REPO_ROOT, "chdk-port", "platform", "g3x", "sub", "110c", "stubs_prototype.S")

BUILD_SCRIPT = os.path.join(REPO_ROOT, "tools", "build_candidate_port2a.py")
VALIDATE_SCRIPT = os.path.join(REPO_ROOT, "tools", "validate_candidate_port2a.py")

CHDK_PORT = os.path.join(REPO_ROOT, "chdk-port")
TOOLCHAIN_BIN = os.path.join(REPO_ROOT, "toolchains", "gcc-arm-none-eabi-5_4-2016q3", "bin")
ARM_CC = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-gcc")
ARM_AR = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-ar")
ARM_NM = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-nm")

# boot_prototype.c pinned SHA-256 with guarded call sites added by p17-trace-integration-r4;
# tracing-off byte identity is verified in test_boot_prototype_unchanged.
BOOT_PROTO_SHA256 = "c3bcbbd3b0891b34d05a64cbae559d0487aeda1ec88e961fddd6cece64479b61"

# Candidate core CFLAGS, copied from tools/build_candidate_port2a.py
# build_candidate_core() step 1 (includes -DLOW_LEVEL). Run with cwd=chdk-port.
CANDIDATE_CFLAGS = [
    "-fno-inline",
    "-Os",
    "-fno-strict-aliasing",
    "-fno-schedule-insns2",
    "-march=armv7-r",
    "-mthumb",
    "-DTHUMB_FW",
    "-Iinclude",
    "-Icore",
    "-Imodules",
    "-Iplatform/g3x",
    "-Iplatform/g3x/sub/110c",
    "-DMEMBASEADDR=0x8000",
    "-DMEMISOSTART=0x3489b4",
    "-DMEMISOSIZE=(&_end-&_start)",
    "-DCAM_DIGIC=60",
    "-DMAXRAMADDR=0x0fffffff",
    "-DROMBASEADDR=0xFC000000",
    "-DVER_CHDK",
    '-DHDK_VERSION="CHDK"',
    '-DBUILD_NUMBER="1.5.0"',
    '-DBUILD_SVNREV="0"',
    "-Wall",
    "-Wno-unused",
    "-Wno-format",
    "-DOPT_CURVES",
    "-DOPT_DEBUGGING",
    "-DOPT_PTP",
    "-DOPT_ARAM_MALLOC",
    "-DARAM_HEAP_START=0x006ce000",
    "-DARAM_HEAP_SIZE=0x00022000",
    "-DOPT_DISABLE_CAM_ERROR=0",
    "-DOPT_ARCHITECTURE=GCC_EABI_THUMB2",
    "-mthumb-interwork",
    "-DLOW_LEVEL",
    '-DPLATFORM="g3x"',
    '-DPLATFORMSUB="110c"',
    "-DPLATFORMID=12968",
    "-DCAMERA_g3x=1",
    "-DCAM_DRYOS_REL=57",
    "-nostdinc",
]

MARKER_CALLS = [
    "G3X_TRACE_ENTRY(0x11, \"E\");",
    "G3X_TRACE_RELOC(0x22, \"R\");",
    "G3X_TRACE_TASK_HOOK(0x33, \"T\");",
    "G3X_TRACE_KBD(0x44, \"K\");",
    "G3X_TRACE_DISPLAY(0x55, \"D\");",
    "G3X_TRACE_ASSERT(0x66, \"A\");",
]


def require_pinned_toolchain():
    for tool in (ARM_CC, ARM_AR, ARM_NM):
        if not os.path.isfile(tool):
            raise unittest.SkipTest(f"Pinned ARM toolchain not available: {tool}")


class TestPort17TraceCore(unittest.TestCase):
    """Host-side unit tests for PORT-17 trace core."""

    @classmethod
    def setUpClass(cls):
        with open(TRACE_H_PATH, "r", encoding="utf-8") as f:
            cls.trace_h = f.read()
        with open(TRACE_C_PATH, "r", encoding="utf-8") as f:
            cls.trace_c = f.read()
        with open(BOOT_PROTO_PATH, "r", encoding="utf-8") as f:
            cls.boot_c = f.read()

    def test_flags_default_off_in_header(self):
        """Compile-time flags G3X_TRACE, G3X_TRACE_FLUSH, G3X_TRACE_LED must default to 0 (OFF)."""
        # Verify G3X_TRACE default 0
        match_trace = re.search(r"#ifndef\s+G3X_TRACE\s*\n#define\s+G3X_TRACE\s+0", self.trace_h)
        self.assertIsNotNone(match_trace, "G3X_TRACE must be guarded by #ifndef and default to 0")

        # Verify G3X_TRACE_FLUSH default 0
        match_flush = re.search(r"#ifndef\s+G3X_TRACE_FLUSH\s*\n#define\s+G3X_TRACE_FLUSH\s+0", self.trace_h)
        self.assertIsNotNone(match_flush, "G3X_TRACE_FLUSH must be guarded by #ifndef and default to 0")

        # Verify G3X_TRACE_LED default 0
        match_led = re.search(r"#ifndef\s+G3X_TRACE_LED\s*\n#define\s+G3X_TRACE_LED\s+0", self.trace_h)
        self.assertIsNotNone(match_led, "G3X_TRACE_LED must be guarded by #ifndef and default to 0")

    def test_flags_evaluate_to_zero_by_default_in_c(self):
        """Verify via C preprocessor/compiler that all three flags evaluate to 0 when omitted."""
        test_c = f"""
        #include "{TRACE_H_PATH}"
        #if G3X_TRACE != 0
        #error "G3X_TRACE is not 0"
        #endif
        #if G3X_TRACE_FLUSH != 0
        #error "G3X_TRACE_FLUSH is not 0"
        #endif
        #if G3X_TRACE_LED != 0
        #error "G3X_TRACE_LED is not 0"
        #endif
        int main(void) {{ return 0; }}
        """
        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as f:
            f.write(test_c)
            tmp_path = f.name
        try:
            cmd = ["gcc", "-fsyntax-only", "-I", os.path.dirname(TRACE_H_PATH), tmp_path]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(res.returncode, 0, f"Host gcc preprocessor evaluation failed:\n{res.stderr}")
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

    def test_record_and_header_constants(self):
        """Header and record layout constants must match documented values."""
        self.assertIn("#define G3X_TRACE_MAGIC             0x43415254U", self.trace_h)
        self.assertIn("#define G3X_TRACE_VERSION           0x00010000U", self.trace_h)
        self.assertIn("#define G3X_TRACE_RECORD_TEXT_LEN   20", self.trace_h)
        self.assertIn("#define G3X_TRACE_CAPACITY          64", self.trace_h)
        self.assertIn("#define G3X_TRACE_RECORD_SIZE       32", self.trace_h)
        self.assertIn("#define G3X_TRACE_HEADER_SIZE       32", self.trace_h)

        # Magic number 0x43415254: ASCII 'TRAC' in memory order ('T','R','A','C')
        # In Little-Endian 32-bit integer word: bytes at offsets 0..3 are [0x54, 0x52, 0x41, 0x43] == b"TRAC"
        self.assertEqual(struct.pack("<I", 0x43415254), b"TRAC")
        self.assertEqual(struct.pack("<I", 0x43415254)[:4], b"TRAC")

    def test_magic_signature_raw_bytes_little_endian(self):
        """Verify packing header magic with struct '<' gives raw bytes b'TRAC' at offsets 0..3."""
        header_raw = struct.pack(
            "<IIIIIIII",
            0x43415254,  # magic
            0x00010000,  # version
            64,          # capacity
            0,           # write_idx
            0,           # dropped_count
            32,          # record_size
            0, 0         # reserved
        )
        self.assertEqual(header_raw[0:4], b"TRAC")

    def test_struct_byte_layout_and_offsets(self):
        """C struct field sizes and offsets must strictly match 32-byte record and header."""
        test_c = f"""
        #include <stddef.h>
        #include <stdio.h>
        #include "{TRACE_H_PATH}"

        int main(void) {{
            if (sizeof(g3x_trace_header_t) != 32) return 1;
            if (sizeof(g3x_trace_record_t) != 32) return 2;
            if (sizeof(g3x_trace_ring_t) != 2080) return 3;

            // Header offsets
            if (offsetof(g3x_trace_header_t, magic) != 0) return 10;
            if (offsetof(g3x_trace_header_t, version) != 4) return 11;
            if (offsetof(g3x_trace_header_t, capacity) != 8) return 12;
            if (offsetof(g3x_trace_header_t, write_idx) != 12) return 13;
            if (offsetof(g3x_trace_header_t, dropped_count) != 16) return 14;
            if (offsetof(g3x_trace_header_t, record_size) != 20) return 15;
            if (offsetof(g3x_trace_header_t, reserved) != 24) return 16;

            // Record offsets
            if (offsetof(g3x_trace_record_t, stage_id) != 0) return 20;
            if (offsetof(g3x_trace_record_t, tick) != 4) return 21;
            if (offsetof(g3x_trace_record_t, pc_lr_val) != 8) return 22;
            if (offsetof(g3x_trace_record_t, text) != 12) return 23;

            // Ring offsets
            if (offsetof(g3x_trace_ring_t, header) != 0) return 30;
            if (offsetof(g3x_trace_ring_t, records) != 32) return 31;

            return 0;
        }}
        """
        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as f:
            f.write(test_c)
            tmp_src = f.name
        tmp_bin = tmp_src + ".out"
        try:
            compile_cmd = ["gcc", "-Wall", "-Werror", "-I", os.path.dirname(TRACE_H_PATH), tmp_src, "-o", tmp_bin]
            res = subprocess.run(compile_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(res.returncode, 0, f"Compilation of layout check failed:\n{res.stderr}")

            run_res = subprocess.run([tmp_bin])
            self.assertEqual(run_res.returncode, 0, f"Layout check binary exited with code {run_res.returncode}")
        finally:
            if os.path.exists(tmp_src):
                os.remove(tmp_src)
            if os.path.exists(tmp_bin):
                os.remove(tmp_bin)

    def test_stage_marker_macros_exist(self):
        """Stage-marker macros must exist for entry, relocation, task hooks, kbd, display."""
        required_macros = [
            "G3X_TRACE_ENTRY",
            "G3X_TRACE_RELOC",
            "G3X_TRACE_TASK_HOOK",
            "G3X_TRACE_KBD",
            "G3X_TRACE_DISPLAY",
            "G3X_TRACE_ASSERT",
            "G3X_TRACE_MARKER",
        ]
        for macro in required_macros:
            self.assertIn(f"#define {macro}", self.trace_h, f"Macro {macro} must be defined in g3x_trace.h")

    def test_stage_marker_macros_expand_to_nothing_when_off(self):
        """When G3X_TRACE is 0, marker macros must expand to ((void)0)."""
        test_c = f"""
        #include "{TRACE_H_PATH}"

        void test_fn(void) {{
            G3X_TRACE_ENTRY(0x1234, "TEST");
            G3X_TRACE_RELOC(0, "RELOC");
            G3X_TRACE_TASK_HOOK(0, "TASK");
            G3X_TRACE_KBD(0, "KBD");
            G3X_TRACE_DISPLAY(0, "DISP");
            G3X_TRACE_ASSERT(0, "FAIL");
            G3X_TRACE_MARKER(1, 0, "M");
        }}

        int main(void) {{
            test_fn();
            return 0;
        }}
        """
        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as f:
            f.write(test_c)
            tmp_src = f.name
        tmp_bin = tmp_src + ".out"
        try:
            compile_cmd = ["gcc", "-Wall", "-Werror", "-I", os.path.dirname(TRACE_H_PATH), tmp_src, "-o", tmp_bin]
            res = subprocess.run(compile_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(res.returncode, 0, f"Macro expansion compilation failed:\n{res.stderr}")
        finally:
            if os.path.exists(tmp_src):
                os.remove(tmp_src)
            if os.path.exists(tmp_bin):
                os.remove(tmp_bin)

    def test_flush_routine_and_todos(self):
        """Flush routine must target A/CHDK/LOGS/TRACE.LOG and cite Q-P17-04, Q-P17-05, Q-P17-07, Q-P17-11."""
        self.assertIn('G3X_TRACE_LOG_PATH          "A/CHDK/LOGS/TRACE.LOG"', self.trace_h)
        self.assertIn("G3X_TRACE_LOG_MAX_SIZE", self.trace_h)

        # Check required TODO citations
        for q in ["Q-P17-04", "Q-P17-05", "Q-P17-07", "Q-P17-11"]:
            self.assertIn(q, self.trace_h, f"g3x_trace.h must cite {q}")
            self.assertIn(q, self.trace_c, f"g3x_trace.c must cite {q}")

    def test_led_fallback_and_todos(self):
        """LED fallback must cite Q-P17-03, Q-P17-06, Q-P17-08, Q-P17-09."""
        for q in ["Q-P17-03", "Q-P17-06", "Q-P17-08", "Q-P17-09"]:
            self.assertIn(q, self.trace_h, f"g3x_trace.h must cite {q}")
            self.assertIn(q, self.trace_c, f"g3x_trace.c must cite {q}")

    def test_compile_time_errors_for_flush_and_led(self):
        """Compiling with G3X_TRACE_FLUSH=1 or G3X_TRACE_LED=1 must fail with #error citing open questions."""
        # 1. Test G3X_TRACE_FLUSH=1
        test_flush_c = f"""
        #define G3X_TRACE 1
        #define G3X_TRACE_FLUSH 1
        #include "{TRACE_H_PATH}"
        int main(void) {{ return 0; }}
        """
        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as f:
            f.write(test_flush_c)
            tmp_src = f.name
        try:
            cmd = ["gcc", "-fsyntax-only", "-I", os.path.dirname(TRACE_H_PATH), tmp_src]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertNotEqual(res.returncode, 0, "Compiling with G3X_TRACE_FLUSH=1 must fail at compile time")
            err_msg = res.stderr
            self.assertIn("G3X_TRACE_FLUSH", err_msg)
            for q in ["Q-P17-04", "Q-P17-05", "Q-P17-07", "Q-P17-11"]:
                self.assertIn(q, err_msg, f"#error message must cite open question {q}")
        finally:
            if os.path.exists(tmp_src):
                os.remove(tmp_src)

        # 2. Test G3X_TRACE_LED=1
        test_led_c = f"""
        #define G3X_TRACE 1
        #define G3X_TRACE_LED 1
        #include "{TRACE_H_PATH}"
        int main(void) {{ return 0; }}
        """
        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as f:
            f.write(test_led_c)
            tmp_src = f.name
        try:
            cmd = ["gcc", "-fsyntax-only", "-I", os.path.dirname(TRACE_H_PATH), tmp_src]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertNotEqual(res.returncode, 0, "Compiling with G3X_TRACE_LED=1 must fail at compile time")
            err_msg = res.stderr
            self.assertIn("G3X_TRACE_LED", err_msg)
            for q in ["Q-P17-03", "Q-P17-06", "Q-P17-08", "Q-P17-09"]:
                self.assertIn(q, err_msg, f"#error message must cite open question {q}")
        finally:
            if os.path.exists(tmp_src):
                os.remove(tmp_src)

    def test_pure_logic_helpers(self):
        """Verify firmware-independent logic: size cap check, serialization, blink pattern."""
        test_c = f"""
        #include <stdint.h>
        #include <stdio.h>
        #include <string.h>
        #include <assert.h>
        #define G3X_TRACE 1
        #include "{TRACE_H_PATH}"
        #include "{TRACE_C_PATH}"

        int main(void) {{
            // 1. Log size cap check (64 KiB cap = 65536 bytes)
            // 1a. Normal within cap
            assert(g3x_trace_check_log_cap(0, 1024) == 1);

            // 1b. Exact fit (current_size + bytes_to_write == 64 KiB accepted)
            assert(g3x_trace_check_log_cap(0, 64 * 1024) == 1);
            assert(g3x_trace_check_log_cap(64 * 1024 - 32, 32) == 1);
            assert(g3x_trace_check_log_cap(32768, 32768) == 1);
            assert(g3x_trace_check_log_cap(64 * 1024, 0) == 1);

            // 1c. One byte over (rejected)
            assert(g3x_trace_check_log_cap(0, 64 * 1024 + 1) == 0);
            assert(g3x_trace_check_log_cap(64 * 1024 - 32, 33) == 0);
            assert(g3x_trace_check_log_cap(64 * 1024 - 31, 32) == 0);

            // 1d. current_size == cap with bytes 0 and 1
            assert(g3x_trace_check_log_cap(64 * 1024, 0) == 1);
            assert(g3x_trace_check_log_cap(64 * 1024, 1) == 0);

            // 1e. current_size > cap
            assert(g3x_trace_check_log_cap(64 * 1024 + 1, 0) == 0);
            assert(g3x_trace_check_log_cap(64 * 1024 + 1, 1) == 0);
            assert(g3x_trace_check_log_cap(100000, 0) == 0);
            assert(g3x_trace_check_log_cap(100000, 10) == 0);

            // 1f. Wrap case: 0xFFFFFFF0 + 32 (rejected)
            assert(g3x_trace_check_log_cap(0xFFFFFFF0U, 32) == 0);

            // 1g. bytes_to_write = 0xFFFFFFFF (rejected)
            assert(g3x_trace_check_log_cap(0, 0xFFFFFFFFU) == 0);
            assert(g3x_trace_check_log_cap(100, 0xFFFFFFFFU) == 0);
            assert(g3x_trace_check_log_cap(64 * 1024, 0xFFFFFFFFU) == 0);
            assert(g3x_trace_check_log_cap(64 * 1024 + 1, 0xFFFFFFFFU) == 0);
            assert(g3x_trace_check_log_cap(0xFFFFFFF0U, 0xFFFFFFFFU) == 0);

            // 2. Record serialization
            g3x_trace_record_t rec;
            rec.stage_id = G3X_STAGE_ENTRY;
            rec.tick = 42;
            rec.pc_lr_val = 0x12345678;
            strncpy(rec.text, "TEST_REC", G3X_TRACE_RECORD_TEXT_LEN);

            char buf[64];
            memset(buf, 0, sizeof(buf));
            int serialized_len = g3x_trace_serialize_record(&rec, buf, sizeof(buf));
            assert(serialized_len == 32);

            // Verify serialized bytes match struct
            assert(memcmp(buf, &rec, 32) == 0);

            // Buffer too small test
            assert(g3x_trace_serialize_record(&rec, buf, 16) == 0);

            // 3. Blink pattern helper
            assert(g3x_trace_get_blink_pattern(0) == 0);
            assert(g3x_trace_get_blink_pattern(-1) == 0);
            assert(g3x_trace_get_blink_pattern(3) == 3);
            assert(g3x_trace_get_blink_pattern(10) == 10);
            assert(g3x_trace_get_blink_pattern(15) == 10); // Capped at 10

            return 0;
        }}
        """
        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as f:
            f.write(test_c)
            tmp_src = f.name
        tmp_bin = tmp_src + ".out"
        try:
            cmd = ["gcc", "-Wall", "-Werror", "-I", os.path.dirname(TRACE_H_PATH), tmp_src, "-o", tmp_bin]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(res.returncode, 0, f"Compilation of pure logic test failed:\n{res.stderr}")

            run_res = subprocess.run([tmp_bin])
            self.assertEqual(run_res.returncode, 0, f"Pure logic test binary exited with code {run_res.returncode}")
        finally:
            if os.path.exists(tmp_src):
                os.remove(tmp_src)
            if os.path.exists(tmp_bin):
                os.remove(tmp_bin)

    def test_log_size_cap_boundary_and_overflow(self):
        """Boundary and wrap testing for g3x_trace_check_log_cap:
        - exact fit (current + bytes == 64 KiB accepted)
        - one byte over (rejected)
        - current_size == cap with bytes 0 and 1
        - current_size > cap
        - wrap case 0xFFFFFFF0 + 32 (rejected)
        - bytes_to_write = 0xFFFFFFFF (rejected)
        """
        test_c = f"""
        #include <stdint.h>
        #include <assert.h>
        #define G3X_TRACE 1
        #include "{TRACE_H_PATH}"
        #include "{TRACE_C_PATH}"

        int main(void) {{
            // Exact fit: current + bytes == 64 KiB (accepted -> 1)
            assert(g3x_trace_check_log_cap(0, 64 * 1024) == 1);
            assert(g3x_trace_check_log_cap(64 * 1024 - 32, 32) == 1);
            assert(g3x_trace_check_log_cap(32768, 32768) == 1);
            assert(g3x_trace_check_log_cap(64 * 1024, 0) == 1);

            // One byte over (rejected -> 0)
            assert(g3x_trace_check_log_cap(0, 64 * 1024 + 1) == 0);
            assert(g3x_trace_check_log_cap(64 * 1024 - 32, 33) == 0);
            assert(g3x_trace_check_log_cap(64 * 1024 - 31, 32) == 0);

            // current_size == cap with bytes 0 and 1
            assert(g3x_trace_check_log_cap(64 * 1024, 0) == 1);
            assert(g3x_trace_check_log_cap(64 * 1024, 1) == 0);

            // current_size > cap
            assert(g3x_trace_check_log_cap(64 * 1024 + 1, 0) == 0);
            assert(g3x_trace_check_log_cap(64 * 1024 + 1, 1) == 0);
            assert(g3x_trace_check_log_cap(100000, 0) == 0);
            assert(g3x_trace_check_log_cap(100000, 10) == 0);

            // Wrap case 0xFFFFFFF0 + 32 (rejected -> 0)
            assert(g3x_trace_check_log_cap(0xFFFFFFF0U, 32) == 0);

            // bytes_to_write = 0xFFFFFFFF (rejected -> 0)
            assert(g3x_trace_check_log_cap(0, 0xFFFFFFFFU) == 0);
            assert(g3x_trace_check_log_cap(100, 0xFFFFFFFFU) == 0);
            assert(g3x_trace_check_log_cap(64 * 1024, 0xFFFFFFFFU) == 0);
            assert(g3x_trace_check_log_cap(64 * 1024 + 1, 0xFFFFFFFFU) == 0);
            assert(g3x_trace_check_log_cap(0xFFFFFFF0U, 0xFFFFFFFFU) == 0);

            return 0;
        }}
        """
        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as f:
            f.write(test_c)
            tmp_src = f.name
        tmp_bin = tmp_src + ".out"
        try:
            cmd = ["gcc", "-Wall", "-Werror", "-I", os.path.dirname(TRACE_H_PATH), tmp_src, "-o", tmp_bin]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(res.returncode, 0, f"Compilation of log cap boundary test failed:\n{res.stderr}")

            run_res = subprocess.run([tmp_bin])
            self.assertEqual(run_res.returncode, 0, f"Log cap boundary test binary exited with code {run_res.returncode}")
        finally:
            if os.path.exists(tmp_src):
                os.remove(tmp_src)
            if os.path.exists(tmp_bin):
                os.remove(tmp_bin)

    def test_no_uncited_firmware_addresses(self):
        """No uncited firmware RAM or ROM address must appear in g3x_trace.h or g3x_trace.c."""
        cited_addresses = {
            0x003489B4, 0x0035F7A0, 0x00366CB0, 0x00009BA4,
            0xD20B0000, 0xFC12D724, 0xFC37EFA7, 0xFC37F077, 0xFC37EFCF,
            0x002B5364, 0x43415254, 0x54524143, 0x00010000, 0x00000000, 0x00000001,
            0x00000002, 0x00000003, 0x00000004, 0x00000005, 0x000000FE,
            0x000000FF,
        }
        for file_content, filename in [(self.trace_h, "g3x_trace.h"), (self.trace_c, "g3x_trace.c")]:
            hex_matches = re.findall(r"0x[0-9a-fA-F]+", file_content)
            for m in hex_matches:
                val = int(m, 16)
                if val >= 0x00010000:  # Ignore small numbers / masks (0x20, 0xFF, etc.)
                    self.assertIn(
                        val, cited_addresses,
                        f"Uncited address {m} found in {filename}"
                    )

    def test_stubs_prototype_unchanged(self):
        """stubs_prototype.S must not change any existing stub address."""
        with open(STUBS_PROTO_PATH, "r", encoding="utf-8") as f:
            stubs_content = f.read()
        self.assertIn("STUB(fc02007e)", stubs_content)
        self.assertIn("STUB2(fc31bfac)", stubs_content)
        self.assertIn("STUB(fc0d0126)", stubs_content)

    def test_boot_prototype_unchanged(self):
        """boot_prototype.c matches pinned digest; tracing-off view is byte-identical to parent."""
        with open(BOOT_PROTO_PATH, "rb") as f:
            digest = hashlib.sha256(f.read()).hexdigest()
        self.assertEqual(digest, BOOT_PROTO_SHA256)

        lines = self.boot_c.splitlines(keepends=True)

        # (a) Parse boot_prototype.c line by line. Each region opened by exactly
        # `#if defined(G3X_TRACE) && G3X_TRACE` must be balanced, with an optional `#else`
        # and a closing `#endif`. Assert that there are exactly 2 such regions and that
        # no other preprocessor conditional mentions G3X_TRACE.
        for line_no, line in enumerate(lines, 1):
            s = line.strip()
            if s.startswith("#") and any(s.startswith(f"#{kw}") for kw in ("if", "ifdef", "ifndef", "elif")):
                if "G3X_TRACE" in s:
                    self.assertEqual(
                        s,
                        "#if defined(G3X_TRACE) && G3X_TRACE",
                        f"Line {line_no}: conditional mentioning G3X_TRACE must be exactly '#if defined(G3X_TRACE) && G3X_TRACE'",
                    )

        regions = []
        in_region = False
        in_else = False
        current_region_lines = []
        region_line_numbers = set()
        tracing_off_lines = []

        for line_no, line in enumerate(lines, 1):
            s = line.strip()
            if s == "#if defined(G3X_TRACE) && G3X_TRACE":
                self.assertFalse(in_region, f"Line {line_no}: nested #if defined(G3X_TRACE) && G3X_TRACE not allowed")
                in_region = True
                in_else = False
                region_line_numbers.add(line_no)
                current_region_lines = [line_no]
                continue
            elif in_region and s == "#else":
                self.assertFalse(in_else, f"Line {line_no}: duplicate #else in region")
                in_else = True
                region_line_numbers.add(line_no)
                continue
            elif in_region and s == "#endif":
                in_region = False
                region_line_numbers.add(line_no)
                regions.append(current_region_lines)
                current_region_lines = []
                continue

            if in_region:
                region_line_numbers.add(line_no)
                if in_else:
                    tracing_off_lines.append(line)
            else:
                tracing_off_lines.append(line)

        self.assertFalse(in_region, "Unclosed #if defined(G3X_TRACE) && G3X_TRACE region at EOF")
        self.assertEqual(len(regions), 2, f"Expected exactly 2 G3X_TRACE regions, found {len(regions)}")

        # (b) Assert that every occurrence of the substring g3x_trace / G3X_TRACE is inside
        # such a region or on its directive lines.
        for line_no, line in enumerate(lines, 1):
            if "g3x_trace" in line or "G3X_TRACE" in line:
                self.assertIn(
                    line_no,
                    region_line_numbers,
                    f"Line {line_no} contains g3x_trace/G3X_TRACE outside of a guarded region: {line!r}",
                )

        # (c) Build the tracing-off view: drop the directive lines and the #if-branch lines,
        # and keep the #else-branch lines. Assert that the SHA-256 of that view, as bytes,
        # EXACTLY equals the parent commit's boot_prototype.c digest
        # f7884eb2078e93a0098299e2665c1069ecbc65c7759d8993fa31e38fbb232e68.
        tracing_off_view = "".join(tracing_off_lines)
        view_digest = hashlib.sha256(tracing_off_view.encode("utf-8")).hexdigest()
        self.assertEqual(
            view_digest,
            "f7884eb2078e93a0098299e2665c1069ecbc65c7759d8993fa31e38fbb232e68",
            "Tracing-off view SHA-256 must exactly equal parent commit boot_prototype.c digest",
        )

        # (d) Keep assertNotIn("g3x_trace", tracing_off_view), and assert that the view contains
        # `b.w     sub_fc05b3c8_my` exactly as in the parent.
        self.assertNotIn("g3x_trace", tracing_off_view)
        self.assertIn("b.w     sub_fc05b3c8_my", tracing_off_view)

    def test_trace_not_wired_into_candidate_build(self):
        """g3x_trace.c must not be wired into the candidate builder in this task."""
        with open(BUILD_SCRIPT, "r", encoding="utf-8") as f:
            self.assertNotIn("g3x_trace", f.read())

    def _preprocess_markers(self, extra_defines):
        """Preprocess the stage markers with the candidate CFLAGS; return the marker body."""
        require_pinned_toolchain()
        snippet = (
            '#include "g3x_trace.h"\n'
            "void p17_marker_probe(void) {\n"
            "P17_BEGIN_MARKERS;\n"
            + "\n".join(MARKER_CALLS)
            + "\nP17_END_MARKERS;\n}\n"
        )
        with tempfile.TemporaryDirectory() as tmp_dir:
            src = os.path.join(tmp_dir, "marker_probe.c")
            with open(src, "w", encoding="utf-8") as f:
                f.write(snippet)
            cmd = [ARM_CC] + CANDIDATE_CFLAGS + extra_defines + ["-E", "-P", src]
            res = subprocess.run(cmd, cwd=CHDK_PORT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(res.returncode, 0, f"Preprocessing markers failed:\n{res.stderr}")
        body = res.stdout.split("P17_BEGIN_MARKERS;", 1)[1].split("P17_END_MARKERS;", 1)[0]
        return body

    def test_low_level_trace_on_markers_expand_to_calls(self):
        """With LOW_LEVEL and G3X_TRACE=1, every marker expands to a g3x_trace_record call."""
        require_pinned_toolchain()
        body = self._preprocess_markers(["-DG3X_TRACE=1"])
        self.assertIn("-DLOW_LEVEL", CANDIDATE_CFLAGS)
        self.assertNotIn("((void)0)", body)
        self.assertEqual(body.count("g3x_trace_record("), len(MARKER_CALLS),
                         f"Each marker must expand to one g3x_trace_record call:\n{body}")
        for stage in ("0x00000001U", "0x00000002U", "0x00000003U",
                      "0x00000004U", "0x00000005U", "0x000000FEU"):
            self.assertIn(stage, body, f"Stage id {stage} missing from marker expansion")
        self.assertIn("g3x_trace_flush()", body)

    def test_low_level_trace_off_markers_expand_to_nothing(self):
        """With LOW_LEVEL and G3X_TRACE=0 (explicit or default), markers expand to no-ops."""
        require_pinned_toolchain()
        for defines in (["-DG3X_TRACE=0"], []):
            body = self._preprocess_markers(defines)
            self.assertNotIn("g3x_trace_record", body)
            self.assertNotIn("g3x_trace_flush", body)
            statements = [s.strip() for s in body.split(";") if s.strip()]
            self.assertEqual(len(statements), len(MARKER_CALLS))
            for stmt in statements:
                self.assertEqual(stmt.replace(" ", ""), "((void)0)", f"Marker must be a no-op, got: {stmt}")

    def _nm_object(self, defines):
        """Compile g3x_trace.c with the candidate CFLAGS plus defines; return nm symbol -> type."""
        require_pinned_toolchain()
        with tempfile.TemporaryDirectory() as tmp_dir:
            obj = os.path.join(tmp_dir, "g3x_trace.o")
            cmd = [ARM_CC] + CANDIDATE_CFLAGS + defines + ["-c", "-o", obj, TRACE_C_PATH]
            res = subprocess.run(cmd, cwd=CHDK_PORT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(res.returncode, 0, f"ARM compile of g3x_trace.c {defines} failed:\n{res.stderr}")
            nm = subprocess.run([ARM_NM, obj], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(nm.returncode, 0, f"nm failed:\n{nm.stderr}")
        syms = {}
        for line in nm.stdout.splitlines():
            parts = line.split()
            if len(parts) >= 2:
                syms[parts[-1]] = parts[-2]
        return syms

    def test_low_level_trace_on_object_defines_recorder(self):
        """Pinned toolchain, candidate CFLAGS (LOW_LEVEL) + G3X_TRACE=1: recorder is compiled in."""
        require_pinned_toolchain()
        syms = self._nm_object(["-DG3X_TRACE=1"])
        for fn in ("g3x_trace_init", "g3x_trace_record", "g3x_trace_flush", "g3x_trace_led_blink",
                   "g3x_trace_mark_entry", "g3x_trace_mark_reloc", "g3x_trace_mark_task_hook",
                   "g3x_trace_mark_kbd", "g3x_trace_mark_display"):
            self.assertEqual(syms.get(fn), "T", f"{fn} must be defined in .text (got {syms.get(fn)})")
        self.assertIn(syms.get("g3x_trace_ring"), ("B", "b", "C"), "g3x_trace_ring must be in bss/common")
        # The recorder makes no firmware calls: no undefined symbols.
        undefined = sorted(name for name, typ in syms.items() if typ == "U")
        self.assertEqual(undefined, [], f"g3x_trace.o must not reference external symbols: {undefined}")

    def test_low_level_trace_off_object_is_empty(self):
        """Pinned toolchain, candidate CFLAGS (LOW_LEVEL), tracing OFF: object defines no symbols."""
        require_pinned_toolchain()
        syms = self._nm_object([])
        self.assertEqual(syms, {}, f"g3x_trace.o must be empty with G3X_TRACE OFF, got {syms}")

    def test_candidate_build_and_validate_invariance(self):
        """Candidate build and validation must pass with G3X_TRACE OFF and preserve PORT-16 layout."""
        require_pinned_toolchain()
        # 1. Run candidate build
        build_res = subprocess.run(
            [sys.executable, "-B", BUILD_SCRIPT],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(build_res.returncode, 0, f"Candidate build failed:\n{build_res.stdout}\n{build_res.stderr}")
        self.assertIn("CANDIDATE BUILD COMPLETE", build_res.stdout)

        # 2. Run candidate validation
        val_res = subprocess.run(
            [sys.executable, "-B", VALIDATE_SCRIPT],
            cwd=REPO_ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(val_res.returncode, 0, f"Candidate validation failed:\n{val_res.stdout}\n{val_res.stderr}")
        self.assertIn("ALL PORT-2A CANDIDATE VALIDATION CHECKS PASSED", val_res.stdout)

        # 3. Verify core symbol addresses in ELF
        elf_path = os.path.join(REPO_ROOT, "candidate_port2a", "candidate_main.elf")
        nm_res = subprocess.run(
            [ARM_NM, elf_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(nm_res.returncode, 0, f"nm failed on {elf_path}:\n{nm_res.stderr}")

        syms = {}
        for line in nm_res.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 3:
                syms[parts[2]] = int(parts[0], 16)

        self.assertEqual(syms.get("_start"), 0x003489B4, "_start must equal PORT-16 address 0x003489B4")
        self.assertEqual(syms.get("boot_witness"), 0x0035F7A0, "boot_witness must equal PORT-16 address 0x0035F7A0")
        self.assertEqual(syms.get("_end"), 0x00366CB0, "_end must equal PORT-16 address 0x00366CB0")
        self.assertEqual(syms.get("link_bss_end"), 0x00366CB0, "link_bss_end must equal PORT-16 address 0x00366CB0")

    def test_trace_on_host_execution_and_ring_wrapping(self):
        """Compile g3x_trace.c on host with G3X_TRACE=1 and verify ring buffer operations."""
        test_c = f"""
        #include <stdio.h>
        #include <string.h>
        #include <assert.h>
        #define G3X_TRACE 1
        #include "{TRACE_H_PATH}"
        #include "{TRACE_C_PATH}"

        int main(void) {{
            // 1. Initial write triggers lazy init
            g3x_trace_record(G3X_STAGE_ENTRY, 100, 0x1234, "ENTRY");
            assert(g3x_trace_ring.header.magic == G3X_TRACE_MAGIC);
            assert(g3x_trace_ring.header.version == G3X_TRACE_VERSION);
            assert(g3x_trace_ring.header.capacity == 64);
            assert(g3x_trace_ring.header.write_idx == 1);
            assert(g3x_trace_ring.header.dropped_count == 0);
            assert(g3x_trace_ring.records[0].stage_id == G3X_STAGE_ENTRY);
            assert(g3x_trace_ring.records[0].tick == 100);
            assert(g3x_trace_ring.records[0].pc_lr_val == 0x1234);
            assert(strcmp((char*)g3x_trace_ring.records[0].text, "ENTRY") == 0);

            // 2. Stage marker helpers
            g3x_trace_mark_entry();
            assert(g3x_trace_ring.header.write_idx == 2);
            assert(g3x_trace_ring.records[1].stage_id == G3X_STAGE_ENTRY);

            g3x_trace_mark_reloc();
            assert(g3x_trace_ring.header.write_idx == 3);
            assert(g3x_trace_ring.records[2].stage_id == G3X_STAGE_RELOC);

            g3x_trace_mark_task_hook();
            assert(g3x_trace_ring.header.write_idx == 4);
            assert(g3x_trace_ring.records[3].stage_id == G3X_STAGE_TASK_HOOK);

            g3x_trace_mark_kbd();
            assert(g3x_trace_ring.header.write_idx == 5);
            assert(g3x_trace_ring.records[4].stage_id == G3X_STAGE_KBD);

            g3x_trace_mark_display();
            assert(g3x_trace_ring.header.write_idx == 6);
            assert(g3x_trace_ring.records[5].stage_id == G3X_STAGE_DISPLAY);

            // 3. Ring wrap & dropped_count test:
            // Fill up to capacity (64 records) -> dropped_count must remain 0
            for (int i = 6; i < 64; i++) {{
                g3x_trace_record(G3X_STAGE_NONE, i + 1, (uint32_t)(i * 10), "FILL");
            }}
            assert(g3x_trace_ring.header.write_idx == 64);
            assert(g3x_trace_ring.header.dropped_count == 0);

            // Write 65th record -> wraps, overwrites slot 0, dropped_count = 1 (65 - 64)
            g3x_trace_record(G3X_STAGE_NONE, 65, 650, "WRAP1");
            assert(g3x_trace_ring.header.write_idx == 65);
            assert(g3x_trace_ring.header.dropped_count == 1);
            assert(g3x_trace_ring.records[0].tick == 65);
            assert(g3x_trace_ring.records[0].pc_lr_val == 650);

            // Write up to 70 records total -> dropped_count = 6 (70 - 64)
            for (int i = 65; i < 70; i++) {{
                g3x_trace_record(G3X_STAGE_NONE, i + 1, (uint32_t)((i + 1) * 10), "WRAP");
            }}
            assert(g3x_trace_ring.header.write_idx == 70);
            assert(g3x_trace_ring.header.dropped_count == 6);
            // Slot 5 was overwritten by 70th record (write_idx 70, slot 5)
            assert(g3x_trace_ring.records[5].tick == 70);
            assert(g3x_trace_ring.records[5].pc_lr_val == 700);

            // 4. Gated flush and LED return safe defaults
            assert(g3x_trace_flush() == -1); // G3X_TRACE_FLUSH disabled
            g3x_trace_led_blink(1);          // G3X_TRACE_LED disabled

            return 0;
        }}
        """
        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as f:
            f.write(test_c)
            tmp_src = f.name
        tmp_bin = tmp_src + ".out"
        try:
            compile_cmd = ["gcc", "-Wall", "-Werror", "-I", os.path.dirname(TRACE_H_PATH), tmp_src, "-o", tmp_bin]
            res = subprocess.run(compile_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(res.returncode, 0, f"Compilation with G3X_TRACE=1 failed:\n{res.stderr}")

            run_res = subprocess.run([tmp_bin])
            self.assertEqual(run_res.returncode, 0, f"Test binary failed with code {run_res.returncode}")
        finally:
            if os.path.exists(tmp_src):
                os.remove(tmp_src)
            if os.path.exists(tmp_bin):
                os.remove(tmp_bin)

    def test_prototype_trace_on_pinned_toolchain_link(self):
        """Build prototype once with -DG3X_TRACE=1 using pinned toolchain and verify link symbols.

        NOTE: This test links the trace object by hand into an isolated test ELF
        (via -Wl,-u,g3x_trace_ring) to verify linker layout invariance, section
        placement in .bss, and 16-byte alignment. The trace module is NOT wired
        into the candidate build or bootloader (which belongs to task p17-trace-integration).
        """
        require_pinned_toolchain()
        arm_cc, arm_ar, arm_nm = ARM_CC, ARM_AR, ARM_NM

        sub_dir = os.path.join(REPO_ROOT, "chdk-port", "platform", "g3x", "sub", "110c")
        candidate_dir = os.path.join(REPO_ROOT, "candidate_port2a")
        chdk_port = os.path.join(REPO_ROOT, "chdk-port")

        with tempfile.TemporaryDirectory() as tmp_dir:
            boot_proto_o = os.path.join(tmp_dir, "boot_prototype_trace.o")
            trace_proto_o = os.path.join(tmp_dir, "g3x_trace.o")
            lib_candidate_a = os.path.join(tmp_dir, "libplatformsub_candidate_trace.a")
            test_elf = os.path.join(tmp_dir, "candidate_trace.elf")

            # 1. Compile boot_prototype.c with -DG3X_TRACE=1
            compile_cmd = [arm_cc] + CANDIDATE_CFLAGS + ["-DG3X_TRACE=1", "-c", "-o", boot_proto_o, BOOT_PROTO_PATH]
            res_cc = subprocess.run(compile_cmd, cwd=chdk_port, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(res_cc.returncode, 0, f"ARM compilation with -DG3X_TRACE=1 failed:\n{res_cc.stderr}")

            # 1b. Compile g3x_trace.c with -DG3X_TRACE=1
            compile_trace_cmd = [arm_cc] + CANDIDATE_CFLAGS + ["-DG3X_TRACE=1", "-c", "-o", trace_proto_o, TRACE_C_PATH]
            res_trace_cc = subprocess.run(compile_trace_cmd, cwd=chdk_port, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(res_trace_cc.returncode, 0, f"ARM compilation of g3x_trace.c with -DG3X_TRACE=1 failed:\n{res_trace_cc.stderr}")

            # 2. Package candidate sub platform archive
            obj_files = [
                boot_proto_o,
                trace_proto_o,
                os.path.join(candidate_dir, "stubs_prototype.o"),
                os.path.join(sub_dir, "stubs_min.o"),
                os.path.join(sub_dir, "stubs_entry.o"),
                os.path.join(sub_dir, "stubs_entry_2.o"),
                os.path.join(sub_dir, "capt_seq.o"),
                os.path.join(sub_dir, "movie_rec.o"),
                os.path.join(sub_dir, "filewrite.o"),
                os.path.join(sub_dir, "main.thm.o"),
                os.path.join(sub_dir, "gui_draw.thm.o"),
                os.path.join(sub_dir, "memmgmt.thm.o"),
                os.path.join(sub_dir, "gui.thm.o"),
                os.path.join(sub_dir, "kbd_process.thm.o"),
                os.path.join(sub_dir, "kbd_common.thm.o"),
                os.path.join(sub_dir, "conf.thm.o"),
                os.path.join(sub_dir, "gui_osd.thm.o"),
                os.path.join(sub_dir, "raw.thm.o"),
                os.path.join(sub_dir, "usb_sync.thm.o"),
                os.path.join(sub_dir, "shooting.thm.o"),
                os.path.join(sub_dir, "camera_info.thm.o"),
                os.path.join(sub_dir, "remotecap.thm.o"),
                os.path.join(sub_dir, "lib_thumb.thm.o"),
                os.path.join(sub_dir, "lang_str.thm.o"),
                os.path.join(sub_dir, "ptp.thm.o"),
            ]
            res_ar = subprocess.run([arm_ar, "cr", lib_candidate_a] + obj_files, cwd=chdk_port)
            self.assertEqual(res_ar.returncode, 0, f"Creating libplatformsub archive failed")

            # 3. Link candidate_trace.elf
            ld_cmd = [
                arm_cc,
                "-nostdlib",
                "-Wl,--allow-shlib-undefined",
                "-Wl,-T,tools/link-boot.ld",
                "-Wl,-N,-Ttext,0x3489b4",
                "-Wl,-u,g3x_trace_ring",
                "-o",
                test_elf,
                "-Wl,--start-group",
                os.path.join(sub_dir, "entry.o"),
                os.path.join(chdk_port, "platform", "g3x", "libplatform.a"),
                lib_candidate_a,
                os.path.join(chdk_port, "lib", "font", ".o2", "libfont.a"),
                os.path.join(chdk_port, "lib", "math", ".o2", "libmath.a"),
                os.path.join(chdk_port, "lib", "lang", ".o2", "liblang.a"),
                os.path.join(chdk_port, "lib", "armutil", ".o2", "libarmutil.a"),
                os.path.join(chdk_port, "lib", "core", ".o2", "libcore.a"),
                "-lgcc",
                "-Wl,--end-group",
            ]
            res_ld = subprocess.run(ld_cmd, cwd=chdk_port, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(res_ld.returncode, 0, f"Candidate link failed:\n{res_ld.stderr}")

            # 4. Check symbols via arm-none-eabi-nm
            res_nm = subprocess.run([arm_nm, test_elf], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            self.assertEqual(res_nm.returncode, 0, f"nm failed on test_elf:\n{res_nm.stderr}")

            sym_addrs = {}
            sym_types = {}
            for line in res_nm.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 3:
                    sym_addrs[parts[2]] = int(parts[0], 16)
                    sym_types[parts[2]] = parts[1]

            # Invariant checks:
            # a. g3x_trace_ring is in .bss
            self.assertIn("g3x_trace_ring", sym_types, "g3x_trace_ring must exist in symbol table")
            self.assertIn(sym_types["g3x_trace_ring"], ("B", "b"), "g3x_trace_ring must be in .bss section")

            # b. g3x_trace_ring is 16-byte aligned
            ring_addr = sym_addrs["g3x_trace_ring"]
            self.assertEqual(ring_addr % 16, 0, f"g3x_trace_ring (0x{ring_addr:08X}) must be 16-byte aligned")

            # c. g3x_trace_ring sits after boot_witness
            witness_addr = sym_addrs["boot_witness"]
            self.assertGreater(ring_addr, witness_addr, "g3x_trace_ring must sit downstream of boot_witness")

            # d. The recorder is linked in (not stubbed out under LOW_LEVEL).
            for fn in ("g3x_trace_init", "g3x_trace_record"):
                self.assertIn(sym_types.get(fn), ("T", "t"), f"{fn} must be linked into .text")

            # e. With tracing ON the recorder's .text sits before .data, so
            # boot_witness moves up from the PORT-16 value; it must never move
            # down. Pinning the ON layout (e.g. a dedicated .g3x_trace section)
            # is p17-trace-integration work under Q-P17-01. The OFF layout is
            # pinned exactly in test_candidate_build_and_validate_invariance.
            self.assertGreaterEqual(witness_addr, 0x0035F7A0,
                                    f"boot_witness (0x{witness_addr:08X}) must not move below 0x0035F7A0")
            self.assertEqual(witness_addr % 16, 0, f"boot_witness (0x{witness_addr:08X}) must stay 16-byte aligned")

            # f. The ring lies inside the image and _end grows by at least ALIGN_UP(sizeof ring, 16)
            end_trace_addr = sym_addrs["_end"]
            expected_ring_size = 2080  # 32 + 64 * 32
            align_up_ring = (expected_ring_size + 15) & ~15
            self.assertLessEqual(ring_addr + expected_ring_size, end_trace_addr,
                                 "g3x_trace_ring must end at or before _end")
            self.assertGreaterEqual(end_trace_addr - 0x00366CB0, align_up_ring,
                                    f"_end must grow by at least ALIGN_UP(sizeof ring, 16)={align_up_ring}")

    def test_python_struct_parser_compatibility(self):
        """Verify exact byte-level unpacking by host Python parser matches specification."""
        # Header: magic(4), version(4), capacity(4), write_idx(4), dropped_count(4), record_size(4), reserved[2](8)
        header_raw = struct.pack(
            "<IIIIIIII",
            0x43415254,  # magic: ASCII "TRAC" in memory order
            0x00010000,  # version
            64,          # capacity
            70,          # write_idx
            6,           # dropped_count: (write_idx - capacity) = 70 - 64 = 6
            32,          # record_size
            0, 0         # reserved
        )
        self.assertEqual(len(header_raw), 32)
        # Verify raw bytes at offsets 0..3 are b"TRAC"
        self.assertEqual(header_raw[:4], b"TRAC")

        magic, ver, cap, widx, drop, rsize, res0, res1 = struct.unpack("<IIIIIIII", header_raw)
        self.assertEqual(magic, 0x43415254)
        self.assertEqual(ver, 0x00010000)
        self.assertEqual(cap, 64)
        self.assertEqual(widx, 70)
        self.assertEqual(drop, 6)
        self.assertEqual(rsize, 32)

        # Record: stage_id(4), tick(4), pc_lr_val(4), text(20s)
        text_bytes = b"CORE_ENTRY\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00"
        record_raw = struct.pack(
            "<III20s",
            0x00000001,  # stage_id = G3X_STAGE_ENTRY
            100,         # tick
            0x003489B4,  # pc_lr_val
            text_bytes
        )
        self.assertEqual(len(record_raw), 32)
        stage, tick, val, text = struct.unpack("<III20s", record_raw)
        self.assertEqual(stage, 1)
        self.assertEqual(tick, 100)
        self.assertEqual(val, 0x003489B4)
        self.assertEqual(text.rstrip(b"\x00").decode("ascii"), "CORE_ENTRY")


if __name__ == "__main__":
    unittest.main()
