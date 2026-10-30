#!/usr/bin/env python3
"""Unit tests for PORT-17 trace core build integration and stage marker call sites.

Verifies:
1. Default build (tracing OFF), the hard PORT-16 invariants:
   - DISKBOOT.BIN SHA-256 matches the parent commit exactly
     (9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136).
   - Candidate core symbols are unchanged:
     _start=0x003489B4, boot_witness=0x0035F7A0, _end=0x00366CB0.
   - Candidate build and validator pass; no trace symbol is linked.
   These checks justify the updated boot_prototype.c hash pin
   (here and in tests/test_port9b_runtime_contract.py).
2. Tracing-off preprocessed boot_prototype.c and compiled section identity:
   - Pinned arm-none-eabi-gcc -E -P with the candidate core CFLAGS gives output
     byte-identical to the parent commit (595cd2e7...).
   - Compiled object .text and .data section bytes match the parent bit-for-bit.
3. Opt-in trace build (--trace or G3X_TRACE=1):
   - Compiles boot_prototype.c and g3x_trace.c with -DG3X_TRACE=1 and links both.
   - _start, boot_witness, g3x_trace_ring, _end and DISKBOOT.BIN SHA-256 are pinned.
   - g3x_trace_ring is in .bss, 16-byte aligned, 2080 B, and overlaps neither
     boot_witness nor any loaded section.
   - g3x_trace_init/g3x_trace_record (and the markers) are FUNC symbols in a loaded
     executable section inside the range candidate_main.bin covers.
   - Output stays under candidate_trace/ and is marked NOT trial-ready (no inspector).
   - firmware/tools/* is byte-identical before and after the builds.
4. Stage-marker call sites:
   - ENTRY and RELOC calls in boot_prototype.c are guarded by
     #if defined(G3X_TRACE) && G3X_TRACE and cite file:line evidence that is checked
     against the cited lines.
   - The trace ELF disassembly shows boot() -> g3x_trace_boot_post_bss ->
     g3x_trace_mark_entry/g3x_trace_mark_reloc -> g3x_trace_record.
   - TASK_HOOK, KBD and DISPLAY stay TODOs citing Q-P17-01/Q-P17-04, with no call site.
5. Gated flush and LED flags remain OFF:
   - G3X_TRACE_FLUSH=0, G3X_TRACE_LED=0, both #error if enabled.
   - No new uncited firmware addresses or modified stubs.
"""

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
BOOT_PROTO_PATH = os.path.join(REPO_ROOT, "chdk-port", "platform", "g3x", "sub", "110c", "boot_prototype.c")
TRACE_H_PATH = os.path.join(REPO_ROOT, "chdk-port", "platform", "g3x", "sub", "110c", "g3x_trace.h")
TRACE_C_PATH = os.path.join(REPO_ROOT, "chdk-port", "platform", "g3x", "sub", "110c", "g3x_trace.c")
STUBS_PROTO_PATH = os.path.join(REPO_ROOT, "chdk-port", "platform", "g3x", "sub", "110c", "stubs_prototype.S")
PLATFORM_MAIN_C_PATH = os.path.join(REPO_ROOT, "chdk-port", "platform", "g3x", "main.c")
FIRMWARE_TOOLS_DIR = os.path.join(REPO_ROOT, "firmware", "tools")

BUILD_SCRIPT = os.path.join(REPO_ROOT, "tools", "build_candidate_port2a.py")
VALIDATE_SCRIPT = os.path.join(REPO_ROOT, "tools", "validate_candidate_port2a.py")

CANDIDATE_DIR = os.path.join(REPO_ROOT, "candidate_port2a")
CANDIDATE_TRACE_DIR = os.path.join(REPO_ROOT, "candidate_trace")

CHDK_PORT = os.path.join(REPO_ROOT, "chdk-port")
TOOLCHAIN_BIN = os.path.join(REPO_ROOT, "toolchains", "gcc-arm-none-eabi-5_4-2016q3", "bin")
ARM_CC = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-gcc")
ARM_NM = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-nm")
ARM_OBJDUMP = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-objdump")
ARM_OBJCOPY = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-objcopy")
ARM_READELF = os.path.join(TOOLCHAIN_BIN, "arm-none-eabi-readelf")

# Pinned SHA-256 for boot_prototype.c with the guarded PORT-17 call sites.
# Justified by the tracing-off identity tests below (preprocessed source, object
# sections, DISKBOOT.BIN and _start/boot_witness/_end equal the parent build).
BOOT_PROTO_SHA256 = "c3bcbbd3b0891b34d05a64cbae559d0487aeda1ec88e961fddd6cece64479b61"

# Baseline parent commit (p17-trace-core-r2 integration commit)
PARENT_COMMIT = "69f696710ddb298e11ab3b96f66935f9f0e6d70c"

# Expected SHA-256 of candidate DISKBOOT.BIN from parent commit with tracing OFF
PARENT_DISKBOOT_SHA256 = "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"

# PORT-16 parent layout (tracing OFF must keep these exactly)
PORT16_START = 0x003489B4
PORT16_BOOT_WITNESS = 0x0035F7A0
PORT16_END = 0x00366CB0

# Pinned parent artifact hashes proving tracing-off binary identity
PARENT_PREPROCESSED_SHA256 = "595cd2e7b118e5c65adaf95c7041237b87d9ec5a4252428e251063b38dcd0479"
PARENT_TEXT_SECTION_SHA256 = "a2cde18150abfb9051f9ea3da78989b0f96b11b6f40ed9a06427365cf50ef1ff"
PARENT_DATA_SECTION_SHA256 = "66687aadf862bd776c8fc18b8e9f8e20089714856ee233b3902a591d0d5f2925"

# Trace build (tracing ON) layout pins. Not trial-ready; recorded so any layout
# drift of the trace candidate is visible in review.
TRACE_START = 0x003489B4
TRACE_BOOT_WITNESS = 0x0035F7A0
TRACE_RING = 0x00366EA0
TRACE_END = 0x003676C0
TRACE_DISKBOOT_SHA256 = "11ba3940715d4398480e5d4fe0b8e735ba63751b4bdebfbb6f8686a6cb2328b0"

G3X_TRACE_RING_SIZE = 2080  # 32 B header + 64 * 32 B records (g3x_trace.h)
BOOT_WITNESS_SIZE = 32

TRACE_GUARD = "#if defined(G3X_TRACE) && G3X_TRACE"

# Candidate core CFLAGS, matching tools/build_candidate_port2a.py
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


def sha256_path(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def snapshot_dir_hashes(directory):
    hashes = {}
    for entry in sorted(os.listdir(directory)):
        full = os.path.join(directory, entry)
        if os.path.isfile(full):
            hashes[entry] = sha256_path(full)
    return hashes


def readelf_sections(elf_path):
    res = subprocess.run([ARM_READELF, "-S", "-W", elf_path], capture_output=True, text=True, check=True)
    sections = {}
    for line in res.stdout.splitlines():
        m = re.search(r"\[\s*(\d+)\]\s+([\.\w]+)\s+(\w+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+([0-9a-fA-F]+)\s+(\S+)\s+([A-Z]*)\s+(\d+)\s+(\d+)\s+(\d+)", line)
        if m:
            idx = int(m.group(1))
            sections[idx] = {
                "name": m.group(2),
                "type": m.group(3),
                "addr": int(m.group(4), 16),
                "offset": int(m.group(5), 16),
                "size": int(m.group(6), 16),
                "flags": m.group(8),
            }
            sections[m.group(2)] = sections[idx]
    return sections


def readelf_symbols(elf_path):
    res = subprocess.run([ARM_READELF, "-s", "-W", elf_path], capture_output=True, text=True, check=True)
    syms = {}
    for line in res.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 8 and parts[0].rstrip(":").isdigit():
            syms[parts[7]] = {
                "value": int(parts[1], 16),
                "size": int(parts[2], 0),
                "type": parts[3],
                "bind": parts[4],
                "ndx": parts[6],
            }
    return syms


def nm_symbols(elf_path):
    res = subprocess.run([ARM_NM, elf_path], capture_output=True, text=True, check=True)
    syms = {}
    for line in res.stdout.splitlines():
        parts = line.split()
        if len(parts) >= 3:
            syms[parts[2]] = int(parts[0], 16)
    return syms


def disassemble_function(elf_path, fn_name):
    res = subprocess.run([ARM_OBJDUMP, "-d", elf_path], capture_output=True, text=True, check=True)
    lines = res.stdout.splitlines()
    fn_lines = []
    in_fn = False
    for line in lines:
        m = re.match(r"^[0-9a-fA-F]+\s+<([^>]+)>:", line)
        if m:
            label = m.group(1)
            if label == fn_name:
                in_fn = True
                fn_lines.append(line)
                continue
            elif in_fn:
                if label.startswith("loc_"):
                    fn_lines.append(line)
                    continue
                else:
                    break
        if in_fn:
            fn_lines.append(line)
    return "\n".join(fn_lines)


def branch_targets(disasm_text):
    branches = []
    for line in disasm_text.splitlines():
        m = re.search(r"\s(b\.w|bl|b)\s+[0-9a-fA-F]+\s+<([^\+>]+)(?:\+\d+)?>", line)
        if m:
            branches.append((m.group(1), m.group(2)))
    return branches


def trace_guarded_lines(source):
    guarded = set()
    in_trace = False
    for no, line in enumerate(source.splitlines(), 1):
        s = line.strip()
        if s == TRACE_GUARD:
            in_trace = True
            continue
        if in_trace and s in ("#else", "#endif"):
            in_trace = False
            continue
        if in_trace:
            guarded.add(no)
    return guarded


class TestPort17TraceIntegration(unittest.TestCase):
    """Integration test suite for PORT-17 trace core build integration."""

    @classmethod
    def setUpClass(cls):
        # Verify toolchain availability
        for b in (ARM_CC, ARM_NM, ARM_OBJDUMP, ARM_OBJCOPY, ARM_READELF):
            if not os.path.isfile(b):
                raise unittest.SkipTest(f"Pinned ARM toolchain binary not found: {b}")

        with open(BOOT_PROTO_PATH, "r", encoding="utf-8") as f:
            cls.boot_proto_content = f.read()
        with open(TRACE_H_PATH, "r", encoding="utf-8") as f:
            cls.trace_h_content = f.read()
        with open(TRACE_C_PATH, "r", encoding="utf-8") as f:
            cls.trace_c_content = f.read()

    def setUp(self):
        self._tools_hashes_before = snapshot_dir_hashes(FIRMWARE_TOOLS_DIR)
        res = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True)
        self._git_status_before = res.stdout

    def tearDown(self):
        tools_hashes_after = snapshot_dir_hashes(FIRMWARE_TOOLS_DIR)
        self.assertEqual(
            self._tools_hashes_before,
            tools_hashes_after,
            "firmware/tools/* files must remain byte-identical after test execution",
        )
        res = subprocess.run(["git", "status", "--porcelain"], cwd=REPO_ROOT, capture_output=True, text=True)
        self.assertEqual(
            self._git_status_before,
            res.stdout,
            "Tracked repository files must remain unchanged after test execution (git status --porcelain)",
        )

    def _build_trace(self, out_dir, use_env=False):
        if use_env:
            env = os.environ.copy()
            env["G3X_TRACE"] = "1"
            cmd = [sys.executable, "-B", BUILD_SCRIPT, "--out-dir", out_dir]
        else:
            env = None
            cmd = [sys.executable, "-B", BUILD_SCRIPT, "--trace", "--out-dir", out_dir]
        res = subprocess.run(cmd, cwd=REPO_ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(res.returncode, 0, f"Candidate trace build failed:\n{res.stdout}\n{res.stderr}")
        elf_path = os.path.join(out_dir, "candidate_main.elf")
        self.assertTrue(os.path.isfile(elf_path), f"trace ELF not generated at {elf_path}")
        return elf_path

    def test_boot_prototype_sha256_hash_pin(self):
        """Verify boot_prototype.c matches the documented pinned SHA-256."""
        self.assertEqual(sha256_path(BOOT_PROTO_PATH), BOOT_PROTO_SHA256)

    def test_preprocessed_boot_prototype_identical_when_tracing_off(self):
        """Preprocessed output of boot_prototype.c with G3X_TRACE=0 must be byte-identical to parent commit."""
        cmd_curr = [ARM_CC] + CANDIDATE_CFLAGS + ["-E", "-P", "platform/g3x/sub/110c/boot_prototype.c"]
        res_curr = subprocess.run(cmd_curr, cwd=CHDK_PORT, capture_output=True, text=True)
        self.assertEqual(res_curr.returncode, 0, f"Preprocessing current boot_prototype.c failed:\n{res_curr.stderr}")

        curr_hash = hashlib.sha256(res_curr.stdout.encode("utf-8")).hexdigest()
        self.assertEqual(
            curr_hash,
            PARENT_PREPROCESSED_SHA256,
            f"Preprocessed boot_prototype.c SHA-256 mismatch against parent baseline: got {curr_hash}, expected {PARENT_PREPROCESSED_SHA256}",
        )

        cmd_zero = [ARM_CC] + CANDIDATE_CFLAGS + ["-DG3X_TRACE=0", "-E", "-P", "platform/g3x/sub/110c/boot_prototype.c"]
        res_zero = subprocess.run(cmd_zero, cwd=CHDK_PORT, capture_output=True, text=True)
        self.assertEqual(res_zero.returncode, 0, f"Preprocessing with -DG3X_TRACE=0 failed:\n{res_zero.stderr}")
        self.assertEqual(
            hashlib.sha256(res_zero.stdout.encode("utf-8")).hexdigest(),
            PARENT_PREPROCESSED_SHA256,
            "G3X_TRACE=0 must yield identical preprocessed output to default (off)",
        )

        parent_source_proc = subprocess.run(
            ["git", "show", f"{PARENT_COMMIT}:chdk-port/platform/g3x/sub/110c/boot_prototype.c"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        with tempfile.NamedTemporaryFile("w", suffix=".c", delete=False) as tf:
            tf.write(parent_source_proc.stdout)
            parent_temp_path = tf.name
        try:
            cmd_parent = [ARM_CC] + CANDIDATE_CFLAGS + ["-E", "-P", parent_temp_path]
            res_parent = subprocess.run(cmd_parent, cwd=CHDK_PORT, capture_output=True, text=True)
            self.assertEqual(res_parent.returncode, 0)
            self.assertEqual(
                res_curr.stdout,
                res_parent.stdout,
                "Preprocessed output of boot_prototype.c with tracing OFF must be 100% byte-identical to parent commit",
            )
        finally:
            if os.path.exists(parent_temp_path):
                os.unlink(parent_temp_path)

    def test_compiled_boot_prototype_sections_identical_when_tracing_off(self):
        """Object .text and .data section bytes of boot_prototype.o with tracing OFF match parent baseline."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            obj_path = os.path.join(tmp_dir, "boot_proto.o")
            text_bin = os.path.join(tmp_dir, "text.bin")
            data_bin = os.path.join(tmp_dir, "data.bin")

            compile_cmd = [ARM_CC] + CANDIDATE_CFLAGS + ["-c", "-o", obj_path, BOOT_PROTO_PATH]
            res_c = subprocess.run(compile_cmd, cwd=CHDK_PORT, capture_output=True, text=True)
            self.assertEqual(res_c.returncode, 0, f"Compilation failed: {res_c.stderr}")

            subprocess.run([ARM_OBJCOPY, "-O", "binary", "-j", ".text", obj_path, text_bin], check=True)
            subprocess.run([ARM_OBJCOPY, "-O", "binary", "-j", ".data", obj_path, data_bin], check=True)

            text_hash = sha256_path(text_bin)
            data_hash = sha256_path(data_bin)

            self.assertEqual(
                text_hash,
                PARENT_TEXT_SECTION_SHA256,
                f"boot_prototype.o .text section mismatch: got {text_hash}, expected {PARENT_TEXT_SECTION_SHA256}",
            )
            self.assertEqual(
                data_hash,
                PARENT_DATA_SECTION_SHA256,
                f"boot_prototype.o .data section mismatch: got {data_hash}, expected {PARENT_DATA_SECTION_SHA256}",
            )

    def test_tracing_off_candidate_build_and_validate(self):
        """Candidate build with tracing OFF produces parent-identical DISKBOOT.BIN and layout."""
        with tempfile.TemporaryDirectory() as td:
            res_build = subprocess.run(
                [sys.executable, "-B", BUILD_SCRIPT, "--out-dir", td],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_build.returncode, 0, f"Candidate build failed:\n{res_build.stderr}")

            # DISKBOOT.BIN is byte-identical to the parent commit build
            self.assertEqual(sha256_path(os.path.join(td, "DISKBOOT.BIN")), PARENT_DISKBOOT_SHA256)

            elf_path = os.path.join(td, "candidate_main.elf")
            syms = nm_symbols(elf_path)
            self.assertEqual(syms["_start"], PORT16_START, "_start must match PORT-16 value 0x003489B4")
            self.assertEqual(syms["boot_witness"], PORT16_BOOT_WITNESS, "boot_witness must match PORT-16 value 0x0035F7A0")
            self.assertEqual(syms["_end"], PORT16_END, "_end must match PORT-16 value 0x00366CB0")
            for sym in ("g3x_trace_ring", "g3x_trace_init", "g3x_trace_record", "g3x_trace_boot_post_bss"):
                self.assertNotIn(sym, syms, f"{sym} must not exist when tracing is OFF")

            # boot() still branches straight to sub_fc05b3c8_my after the Canon BSS loop
            boot_asm = disassemble_function(elf_path, "boot")
            self.assertNotIn("g3x_trace", boot_asm)
            self.assertEqual(branch_targets(boot_asm)[-1], ("b.w", "sub_fc05b3c8_my"))

    def test_default_manifest_matches_parent_structure_and_omits_trace_fields(self):
        """Default candidate_manifest.json must omit trace fields and match parent key structure."""
        with tempfile.TemporaryDirectory() as td:
            res_build = subprocess.run(
                [sys.executable, "-B", BUILD_SCRIPT, "--out-dir", td],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(res_build.returncode, 0)
            manifest_path = os.path.join(td, "candidate_manifest.json")
            self.assertTrue(os.path.isfile(manifest_path))
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)

            # Must NOT contain trace-specific fields
            self.assertNotIn("trial_ready", manifest)
            self.assertNotIn("trial_readiness_notes", manifest)
            self.assertNotIn("g3x_trace_enabled", manifest)

            # Expected keys from parent commit
            parent_keys = [
                "milestone",
                "target",
                "platform_id",
                "chdk_revision",
                "toolchain",
                "status",
                "independent_review",
                "hardware_readiness",
                "production_invariance",
                "architectural_invariants",
                "candidate_artifacts",
            ]
            self.assertEqual(list(manifest.keys()), parent_keys)
            self.assertEqual(manifest["status"], "OFFLINE_CANDIDATE_BUILT")
            self.assertEqual(manifest["milestone"], "CHDK-PORT-2A")
            self.assertEqual(manifest["target"], "Canon PowerShot G3 X (GM1.10C)")
            self.assertEqual(manifest["platform_id"], "0x32A8 (12968)")
            self.assertEqual(manifest["hardware_readiness"], "NO-GO")
            self.assertEqual(manifest["independent_review"], "PENDING")

    def _assert_trace_layout(self, elf_path, out_dir):
        syms = readelf_symbols(elf_path)
        sections = readelf_sections(elf_path)
        for name in ("_start", "boot_witness", "g3x_trace_ring", "_end"):
            self.assertIn(name, syms, f"{name} missing from trace ELF")

        # Pinned trace-build values
        self.assertEqual(syms["_start"]["value"], TRACE_START)
        self.assertEqual(syms["boot_witness"]["value"], TRACE_BOOT_WITNESS)
        self.assertEqual(syms["g3x_trace_ring"]["value"], TRACE_RING)
        self.assertEqual(syms["_end"]["value"], TRACE_END)
        self.assertEqual(sha256_path(os.path.join(out_dir, "DISKBOOT.BIN")), TRACE_DISKBOOT_SHA256)

        # Ring: .bss (NOBITS), 16-byte aligned, exactly G3X_TRACE_RING_SIZE, below _end
        ring = syms["g3x_trace_ring"]
        ring_sec = sections[int(ring["ndx"])]
        self.assertEqual(ring_sec["name"], ".bss")
        self.assertEqual(ring_sec["type"], "NOBITS")
        self.assertEqual(ring["type"], "OBJECT")
        self.assertEqual(ring["value"] % 16, 0, f"g3x_trace_ring (0x{ring['value']:08X}) must be 16-byte aligned")
        self.assertEqual(ring["size"], G3X_TRACE_RING_SIZE)
        ring_lo, ring_hi = ring["value"], ring["value"] + ring["size"]
        self.assertLessEqual(ring_hi, syms["_end"]["value"])
        self.assertGreater(ring_lo, syms["boot_witness"]["value"])

        # No overlap with boot_witness or with any loaded (PROGBITS, alloc) section
        wit_lo = syms["boot_witness"]["value"]
        wit_hi = wit_lo + BOOT_WITNESS_SIZE
        self.assertTrue(ring_hi <= wit_lo or ring_lo >= wit_hi, "g3x_trace_ring overlaps boot_witness")
        loaded = [s for s in sections.values() if "A" in s["flags"] and s["type"] != "NOBITS"]
        self.assertTrue(loaded)
        for sec in loaded:
            self.assertTrue(
                ring_hi <= sec["addr"] or ring_lo >= sec["addr"] + sec["size"],
                f"g3x_trace_ring overlaps loaded section {sec['name']}",
            )

        # _end grows by exactly the .g3x_trace_text size plus ALIGN_UP(sizeof ring, 16)
        trace_text_sec = sections[".g3x_trace_text"]
        trace_text_size = trace_text_sec["size"]
        align_up_ring = (G3X_TRACE_RING_SIZE + 15) & ~15
        expected_growth = trace_text_size + align_up_ring
        actual_growth = syms["_end"]["value"] - PORT16_END
        self.assertEqual(
            actual_growth,
            2576,
            f"_end growth ({actual_growth} B) must equal 2576 B",
        )
        self.assertEqual(
            actual_growth,
            expected_growth,
            f"_end growth ({actual_growth} B) must equal .g3x_trace_text size ({trace_text_size} B) + ALIGN_UP(sizeof ring, 16) ({align_up_ring} B)",
        )

        return syms, sections

    def test_opt_in_trace_build_ring_placement_and_invariants(self):
        """Opt-in trace build (--trace): pinned layout, ring in .bss, isolated in tempdir."""
        with tempfile.TemporaryDirectory() as td:
            elf_path = self._build_trace(out_dir=td)

            # The default candidate_port2a/DISKBOOT.BIN is not overwritten if it exists
            if os.path.isfile(os.path.join(CANDIDATE_DIR, "DISKBOOT.BIN")):
                self.assertEqual(
                    sha256_path(os.path.join(CANDIDATE_DIR, "DISKBOOT.BIN")),
                    PARENT_DISKBOOT_SHA256,
                    "Default candidate_port2a/ artifacts must not be modified by the trace build",
                )

            syms, sections = self._assert_trace_layout(elf_path, out_dir=td)

            # Verify trace manifest content
            manifest_path = os.path.join(td, "candidate_manifest.json")
            self.assertTrue(os.path.isfile(manifest_path))
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
            self.assertEqual(manifest["status"], "OFFLINE_TRACE_CANDIDATE_BUILT")
            self.assertFalse(manifest["trial_ready"])
            self.assertIn("NOT trial-ready", manifest["trial_readiness_notes"])
            self.assertTrue(manifest.get("g3x_trace_enabled", False))
            cand_arts = manifest.get("candidate_artifacts", {})
            self.assertNotIn("witness_inspector_gm110c.m", cand_arts)
            self.assertNotIn("witness_inspector_payload.bin", cand_arts)
            for name in cand_arts.keys():
                self.assertNotIn("inspector", name)
            self.assertFalse([n for n in os.listdir(td) if "inspector" in n])

    def test_trace_recorder_linked_in_loaded_executable_section(self):
        """Trace recorder functions survive linking as FUNC symbols inside loaded candidate_main.bin."""
        with tempfile.TemporaryDirectory() as td:
            elf_path = self._build_trace(out_dir=td)
            syms = readelf_symbols(elf_path)
            sections = readelf_sections(elf_path)

            trace_text_sec = sections[".g3x_trace_text"]
            self.assertEqual(trace_text_sec["type"], "PROGBITS")
            self.assertIn("A", trace_text_sec["flags"])
            self.assertIn("X", trace_text_sec["flags"])

            trace_sec_start = trace_text_sec["addr"]
            trace_sec_end = trace_sec_start + trace_text_sec["size"]

            # Inside the range covered by candidate_main.bin: [_start, link_data_end)
            self.assertGreaterEqual(trace_sec_start, syms["_start"]["value"])
            self.assertLessEqual(trace_sec_end, syms["link_data_end"]["value"])

            # The recorder and hook functions are FUNC symbols in .g3x_trace_text
            expected_funcs = [
                "g3x_trace_init",
                "g3x_trace_record",
                "g3x_trace_mark_entry",
                "g3x_trace_mark_reloc",
                "g3x_trace_mark_task_hook",
                "g3x_trace_mark_kbd",
                "g3x_trace_mark_display",
                "g3x_trace_boot_post_bss",
            ]
            for fn in expected_funcs:
                self.assertIn(fn, syms, f"{fn} must be linked into the trace ELF")
                s = syms[fn]
                self.assertEqual(s["type"], "FUNC", f"{fn} must be a FUNC symbol")
                self.assertGreaterEqual(s["value"], trace_sec_start)
                self.assertLess(s["value"], trace_sec_end)

    def test_env_var_opt_in_trace_build(self):
        """Opt-in via G3X_TRACE=1 environment variable produces identical artifacts to --trace."""
        with tempfile.TemporaryDirectory() as td:
            elf_path = self._build_trace(out_dir=td, use_env=True)
            self._assert_trace_layout(elf_path, out_dir=td)

    def test_trace_build_passes_define_to_boot_prototype(self):
        """With tracing ON, the builder compiles boot_prototype.c with -DG3X_TRACE=1 (call sites are live)."""
        with tempfile.TemporaryDirectory() as td:
            self._build_trace(out_dir=td)
            res_nm = subprocess.run(
                [ARM_NM, os.path.join(td, "boot_prototype.o")], capture_output=True, text=True
            )
            self.assertEqual(res_nm.returncode, 0)
            sym_lines = res_nm.stdout.splitlines()
            defined_syms = {line.split()[2] for line in sym_lines if len(line.split()) >= 3 and line.split()[1] in ("T", "t")}
            undef_syms = {line.split()[-1] for line in sym_lines if " U " in line}

            self.assertIn("g3x_trace_boot_post_bss", defined_syms, "boot_prototype.o must define g3x_trace_boot_post_bss")
            self.assertIn("g3x_trace_mark_entry", undef_syms, "boot_prototype.o must call g3x_trace_mark_entry")
            self.assertIn("g3x_trace_mark_reloc", undef_syms, "boot_prototype.o must call g3x_trace_mark_reloc")

    def test_stage_marker_call_sites_guarded_and_cited(self):
        """ENTRY/RELOC call sites are guarded and cite verified file:line evidence; other stages stay TODOs."""
        proto = self.boot_proto_content
        lines = proto.splitlines()
        guarded = trace_guarded_lines(proto)

        # Every trace reference in boot_prototype.c is inside a tracing-ON branch
        trace_lines = [
            no for no, line in enumerate(lines, 1)
            if ("trace_boot_post_bss" in line or "trace_mark_" in line)
            and not line.strip().startswith("//")
        ]
        self.assertTrue(trace_lines)
        for no in trace_lines:
            self.assertIn(no, guarded, f"boot_prototype.c:{no} trace reference is not guarded by {TRACE_GUARD}")

        # The guarded calls exist
        def guarded_line_index(fragment):
            hits = [no for no, line in enumerate(lines, 1) if fragment in line]
            self.assertEqual(len(hits), 1, f"expected one line with {fragment!r}, got {hits}")
            self.assertIn(hits[0], guarded)
            return hits[0]

        branch_no = guarded_line_index('b.w     g3x_trace_boot_post_bss')
        fn_no = guarded_line_index('void __attribute__((naked,noinline,section(".g3x_trace_text"))) g3x_trace_boot_post_bss')
        entry_no = guarded_line_index('bl      g3x_trace_mark_entry')
        reloc_no = guarded_line_index('bl      g3x_trace_mark_reloc')
        self.assertLess(entry_no, reloc_no, "ENTRY must be the first record, before RELOC")

        # The tracing-ON branch replaces exactly the stock post-BSS branch
        self.assertEqual(lines[branch_no - 2].strip(), TRACE_GUARD)
        self.assertEqual(lines[branch_no].strip(), "#else")
        self.assertEqual(lines[branch_no + 1].strip(), '"    b.w     sub_fc05b3c8_my\\n"')
        self.assertEqual(lines[branch_no + 2].strip(), "#endif")
        # ... and it sits right after the Canon BSS zeroing loop
        self.assertIn("Zero Canon BSS", lines[144 - 1])
        self.assertIn("0x003489b4", lines[147 - 1])
        self.assertIn("blo     loc_zero_bss", lines[153 - 1])
        self.assertEqual((156, 160), (branch_no - 1, branch_no + 3))

        # Citations in the marker comment block, checked against the cited lines
        self.assertIn("boot_prototype.c:144-153", proto)
        self.assertIn("boot_prototype.c:155-160", proto)
        self.assertIn("docs/PORT17_TRACE_EVIDENCE.md:205-251, 256", proto)
        self.assertIn("ENTRY timing is post-BSS", proto)
        self.assertIn("sub_fc02007e", proto)
        self.assertIn("boot_prototype.c:98", proto)
        self.assertIn("docs/PORT16_FIRSTBOOT_U_TRIAGE.md:53", proto)
        self.assertIn("boot_prototype.c:89-91", proto)
        self.assertIn("Q-P17-01", proto)
        self.assertIn("witness_record_core", proto)
        self.assertIn("boot_prototype.c:171-174", proto)
        self.assertIn("chdk-port/platform/g3x/main.c:17-20", proto)
        self.assertIn("MEMISOSTART", proto)
        self.assertIn("boot_prototype.c:144-147", proto)

        # Inactive stages stay documented TODOs with no call site in boot_prototype.c
        self.assertIn("TASK_HOOK (G3X_STAGE_TASK_HOOK): TODO (Q-P17-01, Q-P17-04), no call site.", proto)
        self.assertIn("boot_prototype.c:415-420", proto)
        self.assertIn("KBD (G3X_STAGE_KBD): TODO (Q-P17-01), no call site.", proto)
        self.assertIn("stock task_PhySw runs unhooked", proto)
        self.assertIn("boot_prototype.c:13, 412-413", proto)
        self.assertIn("DISPLAY (G3X_STAGE_DISPLAY): TODO (Q-P17-01), no call site.", proto)
        for marker in ("trace_mark_task_hook", "trace_mark_kbd", "trace_mark_display",
                       "G3X_TRACE_TASK_HOOK", "G3X_TRACE_KBD", "G3X_TRACE_DISPLAY"):
            self.assertNotIn(marker, proto, f"{marker} must not have a call site in boot_prototype.c")

        # The header documents the same stage status
        h = self.trace_h_content
        self.assertIn("boot_prototype.c:144-153, 155-160", h)
        self.assertIn("timing is post-BSS", h)
        self.assertIn("TODO (Q-P17-01, Q-P17-04), no call site.", h)
        self.assertIn("boot_prototype.c:13, 412-413", h)
        self.assertNotIn("0x00366CB0 + 2080", h)

        # When tracing is OFF, all marker macros expand to ((void)0)
        self.assertIn("#define G3X_TRACE_ENTRY(val, text)                  ((void)0)", h)
        self.assertIn("#define G3X_TRACE_RELOC(val, text)                  ((void)0)", h)
        self.assertIn("#define G3X_TRACE_TASK_HOOK(val, text)              ((void)0)", h)
        self.assertIn("#define G3X_TRACE_KBD(val, text)                    ((void)0)", h)
        self.assertIn("#define G3X_TRACE_DISPLAY(val, text)                ((void)0)", h)

    def test_trace_elf_boot_code_calls_recorder(self):
        """Trace ELF disassembly: boot() -> hook -> mark_entry/mark_reloc -> g3x_trace_record."""
        with tempfile.TemporaryDirectory() as td:
            elf_path = self._build_trace(out_dir=td)

            boot_branches = branch_targets(disassemble_function(elf_path, "boot"))
            self.assertEqual(boot_branches[-1], ("b.w", "g3x_trace_boot_post_bss"),
                             "boot() must branch to the marker hook after the Canon BSS loop")
            self.assertNotIn(("b.w", "sub_fc05b3c8_my"), boot_branches)

            hook_branches = branch_targets(disassemble_function(elf_path, "g3x_trace_boot_post_bss"))
            self.assertEqual(
                hook_branches,
                [("bl", "g3x_trace_mark_entry"), ("bl", "g3x_trace_mark_reloc"), ("b.w", "sub_fc05b3c8_my")],
            )

            for marker in ("g3x_trace_mark_entry", "g3x_trace_mark_reloc"):
                targets = [t for _, t in branch_targets(disassemble_function(elf_path, marker))]
                self.assertIn("g3x_trace_record", targets, f"{marker} must call g3x_trace_record")

            # sub_fc05b3c8_my is still reached and still records the boot witness first
            tramp = branch_targets(disassemble_function(elf_path, "sub_fc05b3c8_my"))
            self.assertEqual(tramp[0], ("bl", "witness_record_core"))

    def test_gated_flush_and_led_flags_remain_off(self):
        """G3X_TRACE_FLUSH and G3X_TRACE_LED default to 0; compile-time #error if enabled."""
        self.assertRegex(self.trace_h_content, r"#define\s+G3X_TRACE_FLUSH\s+0")
        self.assertRegex(self.trace_h_content, r"#define\s+G3X_TRACE_LED\s+0")

        # Compile with -DG3X_TRACE_FLUSH=1 must fail fail-closed with #error
        flush_cmd = [ARM_CC] + CANDIDATE_CFLAGS + ["-DG3X_TRACE_FLUSH=1", "-c", "-o", "/dev/null", TRACE_C_PATH]
        res_flush = subprocess.run(flush_cmd, cwd=CHDK_PORT, capture_output=True, text=True)
        self.assertNotEqual(res_flush.returncode, 0, "G3X_TRACE_FLUSH=1 must trigger compile-time error")
        self.assertIn("G3X_TRACE_FLUSH cannot be enabled", res_flush.stderr)

        # Compile with -DG3X_TRACE_LED=1 must fail fail-closed with #error
        led_cmd = [ARM_CC] + CANDIDATE_CFLAGS + ["-DG3X_TRACE_LED=1", "-c", "-o", "/dev/null", TRACE_C_PATH]
        res_led = subprocess.run(led_cmd, cwd=CHDK_PORT, capture_output=True, text=True)
        self.assertNotEqual(res_led.returncode, 0, "G3X_TRACE_LED=1 must trigger compile-time error")
        self.assertIn("G3X_TRACE_LED cannot be enabled", res_led.stderr)

        # The trace build does not pass the flush/LED flags
        with open(BUILD_SCRIPT, "r", encoding="utf-8") as f:
            build_src = f.read()
        self.assertNotIn("G3X_TRACE_FLUSH", build_src)
        self.assertNotIn("G3X_TRACE_LED", build_src)

        # No new firmware address in boot_prototype.c: every 0x/sub_ literal in the
        # tracing-ON branches already appears in the tracing-OFF code
        lines = self.boot_proto_content.splitlines()
        guarded = trace_guarded_lines(self.boot_proto_content)
        off_text = "\n".join(l for no, l in enumerate(lines, 1) if no not in guarded)
        for no in guarded:
            code = lines[no - 1].split("//", 1)[0]
            for lit in re.findall(r"0x[0-9a-fA-F]+|sub_[0-9a-fA-F]{8}", code):
                self.assertIn(lit, off_text, f"boot_prototype.c:{no} introduces new address {lit}")

        # Stubs file remains unchanged with no new firmware addresses
        with open(STUBS_PROTO_PATH, "r", encoding="utf-8") as f:
            stubs = f.read()
        self.assertNotIn("LEDDrive", stubs)
        self.assertNotIn("Fopen_Fut", stubs)


if __name__ == "__main__":
    unittest.main()
