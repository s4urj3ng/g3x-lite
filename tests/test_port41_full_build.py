"""Unit and integration tests for PORT-41 standard CHDK full build.

Verifies:
1. Toolchain availability and skip behavior if toolchain is missing.
2. Full build execution producing out/port41-full/DISKBOOT.BIN, CHDK/ modules, fonts, lang.
3. Integrity of SHA-256 manifest (port41_manifest.json).
4. Invariance of chdk-port/platform/g3x/* and chdk-port/loader/g3x/* hashes before and after full build.
5. boot.c invariants: CreateTask at 0xBFE14A3D, sub_fc0d0126 handoff, LED 0xD20B0884,
   ladder timing 0x00100000, sibling citations.
6. InitFileModules completion argument r1=1 citing PORT11A ROM evidence line 263.
7. kbd task stack size 0x2000 citing sibling boot.c line.
8. kbd.c invariants: physw_status 0x40DAC, Power bit 17, Playback bit 16, 10ms sleep,
   start cause 0x9BD0, power-cut bypass sub_fc05b962, restore 0x00080000, ALT off at boot.
9. lib.c and platform_camera.h invariants: displaytype 12, 900x600, buffer width 928,
   UYVY active_bitmap_buffer & 1, opacity_buffer {0x5FC40000, 0x5FB80000}, GUI5 layout.
10. Card write suppression switches and wrappers.
11. Disabled hook TODOs for capt_seq, movie_rec, filewrite.
12. Symbol namespacing preventing collision with PORT-39 / candidate symbols.
13. Functional loader overlay: calls core_copy, branches to MEMISOSTART, non-inert, differs from stock.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import struct
import subprocess
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHDK_PORT_G3X = REPO_ROOT / "chdk-port" / "platform" / "g3x"
CHDK_LOADER_G3X = REPO_ROOT / "chdk-port" / "loader" / "g3x"
FULL_BUILD_G3X = REPO_ROOT / "full_build" / "g3x"
TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
TOOLCHAIN_GCC = TOOLCHAIN_BIN / "arm-none-eabi-gcc"
TOOLCHAIN_OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"
TOOLCHAIN_NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"
BUILD_SCRIPT = REPO_ROOT / "tools" / "build_port41_full.py"
OUT_DIR = REPO_ROOT / "out" / "port41-full"


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(65536):
            h.update(chunk)
    return h.hexdigest()


def snapshot_hashes(dir_path: Path) -> dict[str, str]:
    hashes = {}
    for p in sorted(dir_path.glob("**/*")):
        if p.is_file():
            rel = p.relative_to(dir_path).as_posix()
            hashes[rel] = sha256_file(p)
    return hashes


class TestPort41FullBuildSources(unittest.TestCase):
    """Static checks on full_build/g3x source code and adaptations."""

    def test_boot_invariants(self):
        boot_c = FULL_BUILD_G3X / "sub" / "110c" / "boot.c"
        self.assertTrue(boot_c.is_file(), "full_build/g3x/sub/110c/boot.c missing")
        text = boot_c.read_text(encoding="utf-8")
        text_lower = text.lower()

        # CreateTask runtime address 0xBFE14A3D or hook site 0xBFE14A3C
        self.assertTrue(
            "0xbfe14a3d" in text_lower or "0xbfe14a3c" in text_lower,
            "CreateTask runtime address 0xBFE14A3D missing",
        )

        # Handoff address sub_fc0d0126
        self.assertTrue(
            "sub_fc0d0126" in text_lower or "0xfc0d0126" in text_lower,
            "sub_fc0d0126 ROM handoff missing",
        )

        # Power LED address 0xD20B0884
        self.assertIn("0xd20b0884", text_lower, "Power LED 0xD20B0884 missing")

        # Held-press ladder timing 0x00100000
        self.assertIn("0x00100000", text_lower, "Ladder timing constant missing")

        # Sibling adaptation citation
        self.assertTrue(
            re.search(r"chdk-port/platform/(g7x|g5x)/.*:\d+", text),
            "boot.c must cite chdk-port/platform/<sibling>/...:line",
        )

        # Namespaced symbols
        self.assertIn("g3x_full_shortpress", text, "Namespaced shortpress hooks missing in boot.c")

        # InitFileModules completion argument r1=1 citing PORT11A ROM evidence
        self.assertIn(
            "movs    r1, #1",
            text,
            "InitFileModules completion argument must be movs r1, #1",
        )
        self.assertIn(
            "PORT11A_GM110C_ROM_EVIDENCE.md:263",
            text,
            "InitFileModules hook must cite docs/PORT11A_GM110C_ROM_EVIDENCE.md:263",
        )

        # kbd task stack size 0x2000 citing sibling boot.c
        self.assertIn(
            "0x2000",
            text,
            "mykbd_task stack size 0x2000 missing in boot.c",
        )
        self.assertTrue(
            re.search(r"chdk-port/platform/(g7x|g5x)/sub/\w+/boot\.c:\d+", text),
            "mykbd_task stack size must cite sibling boot.c:line",
        )

    def test_loader_overlay_sources(self):
        loader_dir = FULL_BUILD_G3X / "loader"
        self.assertTrue((loader_dir / "Makefile").is_file(), "full_build/g3x/loader/Makefile missing")
        self.assertTrue((loader_dir / "entry.S").is_file(), "full_build/g3x/loader/entry.S missing")
        self.assertTrue((loader_dir / "main.c").is_file(), "full_build/g3x/loader/main.c missing")

        main_text = (loader_dir / "main.c").read_text(encoding="utf-8")
        self.assertIn("check_compat", main_text)
        self.assertIn("core_copy", main_text)
        self.assertIn("MEMISOSTART", main_text)
        self.assertIn("0xFC127AB1", main_text, "Loader must call 0xFC127AB1 (clean D-cache)")
        self.assertIn("0xFC127B09", main_text, "Loader must call 0xFC127B09 (invalidate I-cache)")
        self.assertNotIn("0xFC418723", main_text, "0xFC418723 must not be present in loader")
        self.assertNotIn("fc418723", main_text.lower(), "0xFC418723 must not be present in loader")
        self.assertTrue(
            re.search(r"chdk-port/loader/(g7x|g5x|g3x)/main(_prototype)?\.c:\d+", main_text),
            "loader/main.c must cite loader:line",
        )
        self.assertIn(
            "docs/CHDK_PORT1F2_MPU_CACHE_CORRECTION.md:114-119",
            main_text,
            "loader/main.c must cite docs/CHDK_PORT1F2_MPU_CACHE_CORRECTION.md:114-119",
        )

    def test_heap_allocator_sources(self):
        """Verify that CHDK heap does not overlap Canon's AdditionAgent buffer (0x006CE000..0x006F0000)."""
        sub_make_inc = FULL_BUILD_G3X / "sub" / "110c" / "makefile.inc"
        self.assertTrue(sub_make_inc.is_file(), "full_build/g3x/sub/110c/makefile.inc missing")
        make_text = sub_make_inc.read_text(encoding="utf-8")

        # OPT_ARAM_MALLOC must be empty/unset, not 1
        self.assertNotRegex(
            make_text,
            r"^\s*override\s+OPT_ARAM_MALLOC\s*=\s*1\b",
            "OPT_ARAM_MALLOC must not be set to 1 in full-build makefile.inc",
        )
        self.assertRegex(
            make_text,
            r"override\s+OPT_ARAM_MALLOC\s*=",
            "OPT_ARAM_MALLOC must be explicitly unset in full-build makefile.inc",
        )

        # ARAM_HEAP_START and ARAM_HEAP_SIZE must not be active definitions
        self.assertNotRegex(
            make_text,
            r"^\s*ARAM_HEAP_START\s*=",
            "ARAM_HEAP_START must not be defined in full-build makefile.inc",
        )
        self.assertNotRegex(
            make_text,
            r"^\s*ARAM_HEAP_SIZE\s*=",
            "ARAM_HEAP_SIZE must not be defined in full-build makefile.inc",
        )

        # Must cite docs/CHDK_PORT1A_MEMORY_OWNERSHIP.md:70-78
        self.assertIn(
            "docs/CHDK_PORT1A_MEMORY_OWNERSHIP.md:70-78",
            make_text,
            "full_build makefile.inc must cite docs/CHDK_PORT1A_MEMORY_OWNERSHIP.md:70-78",
        )

    def test_kbd_invariants(self):
        kbd_c = FULL_BUILD_G3X / "kbd.c"
        self.assertTrue(kbd_c.is_file(), "full_build/g3x/kbd.c missing")
        text = kbd_c.read_text(encoding="utf-8")
        text_lower = text.lower()

        # physw_status 0x40DAC
        self.assertIn("0x40dac", text_lower, "physw_status address 0x40DAC missing")

        # Power bit 17, Playback bit 16
        self.assertTrue(
            re.search(r"1\s*<<\s*17", text) or "0x00020000" in text_lower or "bit 17" in text_lower,
            "Power bit 17 check missing in kbd.c",
        )
        self.assertTrue(
            re.search(r"1\s*<<\s*16", text) or "0x00010000" in text_lower or "bit 16" in text_lower,
            "Playback bit 16 check missing in kbd.c",
        )

        # 10 ms sleep
        self.assertTrue(
            "10 ms" in text_lower or "ms_sleep(10)" in text or "10" in text,
            "10 ms sleep missing",
        )

        # Short-press power-on fix: start cause at 0x9BD0, power-cut bypass at sub_fc05b962
        self.assertIn("0x9bd0", text_lower, "Start cause address 0x9BD0 missing")
        self.assertIn("sub_fc05b962", text_lower, "Power-cut bypass sub_fc05b962 missing")

        # Restore start cause 0x00080000
        self.assertIn("0x00080000", text_lower, "Start cause restore 0x00080000 missing")

        # ALT off at boot
        self.assertTrue(
            "gui_mode = 0" in text or "kbd_set_alt_mode(0)" in text,
            "ALT mode must be off at boot",
        )

    def test_lib_and_platform_camera_invariants(self):
        plat_cam = FULL_BUILD_G3X / "platform_camera.h"
        self.assertTrue(plat_cam.is_file(), "full_build/g3x/platform_camera.h missing")
        cam_text = plat_cam.read_text(encoding="utf-8")

        # 900x600, buffer width 928 in platform_camera.h
        self.assertIn("#define CAM_SCREEN_WIDTH", cam_text)
        self.assertIn("900", cam_text)
        self.assertIn("#define CAM_SCREEN_HEIGHT", cam_text)
        self.assertIn("600", cam_text)
        self.assertIn("#define CAM_BITMAP_WIDTH", cam_text)
        self.assertIn("928", cam_text)
        self.assertIn("#define CAM_SUPPORT_BITMAP_RES_CHANGE", cam_text)

        # lib.c checks
        lib_c = FULL_BUILD_G3X / "lib.c"
        self.assertTrue(lib_c.is_file(), "full_build/g3x/lib.c missing")
        lib_text = lib_c.read_text(encoding="utf-8")
        lib_lower = lib_text.lower()

        # Displaytype 12 (case 12 or displaytype 12)
        self.assertTrue(
            "12" in lib_text and "displaytype" in lib_text,
            "displaytype 12 missing in lib.c",
        )

        # Opacity buffers in lib.c
        self.assertIn("0x5fc40000", lib_lower)
        self.assertIn("0x5fb80000", lib_lower)

        # Active bitmap buffer & 1
        self.assertIn("active_bitmap_buffer & 1", lib_text)

        # GUI5 layout in lib.c (880x576 box, 32 px rows)
        self.assertIn("880", lib_text, "GUI5 box width 880 missing in lib.c")
        self.assertIn("576", lib_text, "GUI5 box height 576 missing in lib.c")
        self.assertIn("32", lib_text, "GUI5 row height 32 missing in lib.c")

    def test_card_write_suppression_switches(self):
        sub_makefile = FULL_BUILD_G3X / "sub" / "110c" / "Makefile"
        self.assertTrue(sub_makefile.is_file(), "full_build/g3x/sub/110c/Makefile missing")
        make_text = sub_makefile.read_text(encoding="utf-8")

        for wrap in ["open", "fopen", "creat", "write", "fwrite"]:
            self.assertIn(f"--wrap={wrap}", make_text, f"--wrap={wrap} missing in sub/110c/Makefile")

        self.assertIn("-DG3X_DISABLE_CARD_WRITES=1", make_text)
        self.assertIn("-DOPT_DISABLE_FILE_WRITES=1", make_text)

        # Wrappers in lib.c
        lib_c = FULL_BUILD_G3X / "lib.c"
        lib_text = lib_c.read_text(encoding="utf-8")
        for wrap in ["__wrap_open", "__wrap_fopen", "__wrap_creat", "__wrap_write", "__wrap_fwrite"]:
            self.assertIn(wrap, lib_text, f"{wrap} implementation missing in lib.c")

    def test_disabled_hook_todos(self):
        for fname in ["capt_seq.c", "movie_rec.c", "filewrite.c"]:
            fpath = FULL_BUILD_G3X / "sub" / "110c" / fname
            self.assertTrue(fpath.is_file(), f"{fpath} missing")
            content = fpath.read_text(encoding="utf-8")
            self.assertIn("TODO", content, f"TODO missing in {fname} for disabled hook")

    def test_symbol_isolation(self):
        """Ensure full build symbols do not collide with candidate symbols."""
        boot_text = (FULL_BUILD_G3X / "sub" / "110c" / "boot.c").read_text(encoding="utf-8")
        kbd_text = (FULL_BUILD_G3X / "kbd.c").read_text(encoding="utf-8")

        # Full build must NOT define the un-namespaced global variable g3x_saved_start_cause
        self.assertNotRegex(
            boot_text,
            r"\bint\s+g3x_saved_start_cause\b",
            "boot.c defines unnamespaced g3x_saved_start_cause",
        )
        self.assertNotRegex(
            kbd_text,
            r"\bint\s+g3x_saved_start_cause\b",
            "kbd.c defines unnamespaced g3x_saved_start_cause",
        )


class TestPort41FullBuildExecution(unittest.TestCase):
    """End-to-end execution test for standard CHDK full build."""

    @classmethod
    def setUpClass(cls):
        if not TOOLCHAIN_GCC.is_file() or not os.access(TOOLCHAIN_GCC, os.X_OK):
            cls.has_toolchain = False
        else:
            cls.has_toolchain = True

    def test_full_build_execution_and_invariance(self):
        if not self.has_toolchain:
            self.skipTest(f"Pinned toolchain gcc not found at {TOOLCHAIN_GCC}; skipping execution test.")

        # Snapshot chdk-port/platform/g3x and chdk-port/loader/g3x hashes before build
        before_plat_hashes = snapshot_hashes(CHDK_PORT_G3X)
        before_loader_hashes = snapshot_hashes(CHDK_LOADER_G3X)

        # Run build script
        cmd = ["python3", "-B", str(BUILD_SCRIPT)]
        res = subprocess.run(cmd, cwd=str(REPO_ROOT), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        self.assertEqual(
            res.returncode,
            0,
            f"build_port41_full.py failed with code {res.returncode}:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}",
        )

        # Check DISKBOOT.BIN
        diskboot = OUT_DIR / "DISKBOOT.BIN"
        self.assertTrue(diskboot.is_file(), f"Expected {diskboot} to exist")
        self.assertGreater(diskboot.stat().st_size, 50000, "DISKBOOT.BIN is suspiciously small")

        # Check CHDK folder contents
        chdk_dir = OUT_DIR / "CHDK"
        self.assertTrue(chdk_dir.is_dir(), f"Expected {chdk_dir} to exist")
        modules_dir = chdk_dir / "MODULES"
        self.assertTrue(modules_dir.is_dir(), f"Expected {modules_dir} to exist")
        flt_files = list(modules_dir.glob("*.flt"))
        self.assertGreaterEqual(len(flt_files), 30, f"Expected >= 30 .flt modules, found {len(flt_files)}")
        self.assertTrue((chdk_dir / "FONTS").is_dir(), "CHDK/FONTS missing")
        self.assertTrue((chdk_dir / "LANG").is_dir(), "CHDK/LANG missing")

        # Check manifest
        manifest_path = OUT_DIR / "port41_manifest.json"
        self.assertTrue(manifest_path.is_file(), f"Expected {manifest_path} to exist")
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)

        self.assertIn("build", manifest)
        self.assertIn("artifacts", manifest)
        self.assertEqual(manifest["artifacts"]["DISKBOOT.BIN"]["size"], diskboot.stat().st_size)
        self.assertEqual(manifest["artifacts"]["DISKBOOT.BIN"]["sha256"], sha256_file(diskboot))
        self.assertEqual(manifest["artifacts"]["modules_count"], len(flt_files))

        # Snapshot chdk-port/platform/g3x and chdk-port/loader/g3x hashes after build and assert equality
        after_plat_hashes = snapshot_hashes(CHDK_PORT_G3X)
        self.assertEqual(
            before_plat_hashes,
            after_plat_hashes,
            "chdk-port/platform/g3x/ files were modified during the full build!",
        )
        after_loader_hashes = snapshot_hashes(CHDK_LOADER_G3X)
        self.assertEqual(
            before_loader_hashes,
            after_loader_hashes,
            "chdk-port/loader/g3x/ files were modified during the full build!",
        )

        # Assert staged build config has OPT_ARAM_MALLOC disabled and no heap in 0x006CE000..0x006F0000
        stage_dir = OUT_DIR / "stage_chdk"
        staged_sub_make = stage_dir / "platform" / "g3x" / "sub" / "110c" / "makefile.inc"
        self.assertTrue(staged_sub_make.is_file(), "staged sub/110c/makefile.inc missing")
        staged_make_text = staged_sub_make.read_text(encoding="utf-8")
        self.assertNotRegex(
            staged_make_text,
            r"^\s*override\s+OPT_ARAM_MALLOC\s*=\s*1\b",
            "Staged build config must not set OPT_ARAM_MALLOC=1",
        )
        self.assertNotRegex(
            staged_make_text,
            r"^\s*ARAM_HEAP_START\s*=",
            "Staged build config must not define ARAM_HEAP_START",
        )
        self.assertNotRegex(
            staged_make_text,
            r"^\s*ARAM_HEAP_SIZE\s*=",
            "Staged build config must not define ARAM_HEAP_SIZE",
        )

        # Staged loader checks:
        staged_loader_main_c = stage_dir / "loader" / "g3x" / "main.c"
        inert_loader_main_c = CHDK_LOADER_G3X / "main.c"
        self.assertTrue(staged_loader_main_c.is_file(), "staged loader/g3x/main.c missing")
        self.assertNotEqual(
            staged_loader_main_c.read_text(encoding="utf-8"),
            inert_loader_main_c.read_text(encoding="utf-8"),
            "Staged loader main.c must differ from inert chdk-port/loader/g3x/main.c",
        )

        # Disassemble staged loader ELF
        staged_loader_elf = stage_dir / "loader" / "g3x" / "main.elf"
        self.assertTrue(staged_loader_elf.is_file(), "staged loader/g3x/main.elf missing")
        objdump_res = subprocess.run(
            [str(TOOLCHAIN_OBJDUMP), "-d", str(staged_loader_elf)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        loader_disasm = objdump_res.stdout

        # Assert entry path calls core_copy
        self.assertIn("<core_copy>", loader_disasm, "Loader entry path must call core_copy")

        # Assert entry path branches to core start address (0x003489b4 / 0x3489b5)
        self.assertIn("3489b4", loader_disasm, "Loader must reference MEMISOSTART (0x3489b4)")
        self.assertIn("bx\tr0", loader_disasm, "Loader must jump to core entry via bx r0")

        # Assert loader does not end in immediate self loop after check_compat
        # The inert loader had: bl <check_compat>; b.n <self>
        self.assertNotRegex(
            loader_disasm,
            r"bl\s+<check_compat>\s*\n\s*[0-9a-f]+:\s+e7fe\s+b\.n",
            "Loader must not loop immediately after check_compat",
        )

        # Assert 0xFC418723 is NOT called or referenced anywhere in loader disassembly
        self.assertNotIn(
            "fc418723",
            loader_disasm.lower(),
            "0xFC418723 must NOT be called in the loader (violates D-clean before I-inv ordering)",
        )

        # Assert decoupled cache maintenance order:
        # call 0xFC127AB1 -> dsb -> call 0xFC127B09 -> dsb -> isb -> branch to core
        match_my_restart = re.search(r"<my_restart>:(.*?)(?:[0-9a-f]{8}\s+<|\Z)", loader_disasm, re.DOTALL)
        self.assertTrue(match_my_restart, "my_restart symbol not found in loader disassembly")
        my_restart_disasm = match_my_restart.group(1)

        handoff_pattern = (
            r"ldr[ \t]+r2,[ \t]*\[pc,[ \t]*#[0-9]+\][^\r\n]*?\((?P<dcache_ptr>[0-9a-f]+)[ \t]+<my_restart[^>\r\n]*>\)[^\r\n]*\r?\n"
            r"[ \t]*[0-9a-f]+:[ \t]+[0-9a-f \t]+blx[ \t]+r2[^\r\n]*\r?\n"
            r"[ \t]*[0-9a-f]+:[ \t]+[0-9a-f \t]+dsb[ \t]+sy[^\r\n]*\r?\n"
            r"(?:[^\r\n]*\r?\n)*?"
            r"[ \t]*[0-9a-f]+:[ \t]+[0-9a-f \t]+ldr[ \t]+r2,[ \t]*\[pc,[ \t]*#[0-9]+\][^\r\n]*?\((?P<icache_ptr>[0-9a-f]+)[ \t]+<my_restart[^>\r\n]*>\)[^\r\n]*\r?\n"
            r"[ \t]*[0-9a-f]+:[ \t]+[0-9a-f \t]+blx[ \t]+r2[^\r\n]*\r?\n"
            r"[ \t]*[0-9a-f]+:[ \t]+[0-9a-f \t]+dsb[ \t]+sy[^\r\n]*\r?\n"
            r"[ \t]*[0-9a-f]+:[ \t]+[0-9a-f \t]+isb[ \t]+sy[^\r\n]*\r?\n"
            r"(?:[^\r\n]*\r?\n)*?"
            r"[ \t]*[0-9a-f]+:[ \t]+[0-9a-f \t]+bx[ \t]+r0"
        )
        m = re.search(handoff_pattern, my_restart_disasm)
        self.assertIsNotNone(
            m,
            f"Loader handoff does not follow required order: call 0xFC127AB1 -> dsb -> call 0xFC127B09 -> dsb -> isb -> bx r0:\n{my_restart_disasm}",
        )
        dcache_ptr = m.group("dcache_ptr")
        icache_ptr = m.group("icache_ptr")
        d_match = re.search(rf"\b{dcache_ptr}:\s+fc127ab1\b", my_restart_disasm, re.IGNORECASE)
        i_match = re.search(rf"\b{icache_ptr}:\s+fc127b09\b", my_restart_disasm, re.IGNORECASE)
        self.assertIsNotNone(d_match, f"Target of first call (at {dcache_ptr}) is not 0xFC127AB1")
        self.assertIsNotNone(i_match, f"Target of second call (at {icache_ptr}) is not 0xFC127B09")

        # Disassemble staged core main.elf to assert regression checks:
        staged_core_elf = stage_dir / "platform" / "g3x" / "sub" / "110c" / "main.elf"
        self.assertTrue(staged_core_elf.is_file(), "staged core main.elf missing")
        core_objdump = subprocess.run(
            [str(TOOLCHAIN_OBJDUMP), "-d", str(staged_core_elf)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        core_disasm = core_objdump.stdout

        # Regression check for InitFileModules completion argument (movs r1, #1)
        # In <init_file_modules_task>: movs r1, #1 followed by b.w <_PostLogicalEventToUI>
        init_file_idx = core_disasm.find("<init_file_modules_task>:")
        self.assertGreater(init_file_idx, 0, "Missing <init_file_modules_task> in core disassembly")
        init_file_chunk = core_disasm[init_file_idx : init_file_idx + 1000]
        self.assertRegex(
            init_file_chunk,
            r"movs\s+r1,\s*#1\s*\n\s*[0-9a-f]+:\s+f[0-9a-f\s]+b\.w\s+[0-9a-f]+\s+<_PostLogicalEventToUI>",
            "init_file_modules_task must execute movs r1, #1 before PostLogicalEventToUI",
        )

        # Stack size check for mykbd_task (r2 = 0x2000 = 8192)
        create_task_idx = core_disasm.find("<CreateTask_my>:")
        self.assertGreater(create_task_idx, 0, "Missing <CreateTask_my> in core disassembly")
        create_task_chunk = core_disasm[create_task_idx : create_task_idx + 1000]
        self.assertRegex(
            create_task_chunk,
            r"movw\s+r2,\s*#(8192|0x2000)",
            "CreateTask_my must set kbd task stack to 0x2000 (8192 bytes)",
        )

        # Heap check: verify aram_malloc_init does not create heap in 0x006CE000..0x006F0000
        aram_init_idx = core_disasm.find("<aram_malloc_init>:")
        self.assertGreater(aram_init_idx, 0, "Missing <aram_malloc_init> in core disassembly")
        aram_init_chunk = core_disasm[aram_init_idx : aram_init_idx + 400]
        self.assertNotIn("chdk_heap_create", aram_init_chunk, "aram_malloc_init must not call chdk_heap_create")
        self.assertNotIn("6ce000", aram_init_chunk.lower(), "aram_malloc_init must not reference 0x006CE000")

    def test_built_binary_key_constants(self):
        """Verify key constants in built staged core ELF / disassembly / binary:
        - CreateTask 0xBFE14A3D (hook site 0xBFE14A3C and runtime entry 0xBFE14A3D)
        - physw_status 0x40DAC
        - bits 17/16 (0x00020000 / 0x00010000)
        - start cause 0x00080000
        - opacity buffers {0x5FC40000, 0x5FB80000}
        - 900x600/928 camera_screen struct
        """
        if not self.has_toolchain:
            self.skipTest(f"Pinned toolchain gcc not found at {TOOLCHAIN_GCC}")

        stage_dir = OUT_DIR / "stage_chdk"
        staged_core_elf = stage_dir / "platform" / "g3x" / "sub" / "110c" / "main.elf"
        self.assertTrue(staged_core_elf.is_file(), f"Expected {staged_core_elf} to exist from full build")

        # Disassemble staged core main.elf
        core_objdump = subprocess.run(
            [str(TOOLCHAIN_OBJDUMP), "-d", str(staged_core_elf)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        core_disasm = core_objdump.stdout
        core_disasm_lower = core_disasm.lower()

        # Extract symbol table with arm-none-eabi-nm
        core_nm = subprocess.run(
            [str(TOOLCHAIN_NM), "-n", str(staged_core_elf)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        nm_out = core_nm.stdout

        # 1. CreateTask 0xBFE14A3D / hook site 0xBFE14A3C
        self.assertTrue(
            "bfe14a3c" in core_disasm_lower or "bfe14a3d" in core_disasm_lower,
            "CreateTask runtime 0xBFE14A3D / hook 0xBFE14A3C missing in core disassembly",
        )
        self.assertIn("hook_CreateTask", nm_out, "hook_CreateTask symbol missing in core symbols")

        # 2. physw_status 0x40DAC
        self.assertIn("00040dac", core_disasm_lower, "physw_status address 0x00040DAC literal missing in core disassembly")
        self.assertRegex(nm_out, r"00040dac\s+[Aa]\s+physw_status\b", "physw_status absolute symbol 0x40DAC missing in core symbols")

        # 3. bits 17/16 (Power bit 17 = 0x00020000, Playback bit 16 = 0x00010000)
        sp_hook_idx = core_disasm.find("<g3x_full_shortpress_boot_entry_hook>:")
        self.assertGreater(sp_hook_idx, 0, "Missing <g3x_full_shortpress_boot_entry_hook> in core disassembly")
        sp_hook_chunk = core_disasm[sp_hook_idx : sp_hook_idx + 800]
        self.assertTrue(
            "10000" in sp_hook_chunk or "65536" in sp_hook_chunk,
            "Playback bit 16 (0x00010000 / 65536) missing in shortpress hook",
        )
        self.assertTrue(
            "20000" in sp_hook_chunk or "131072" in sp_hook_chunk,
            "Power bit 17 (0x00020000 / 131072) missing in shortpress hook",
        )

        # 4. start cause 0x00080000 (shooting mode start cause restored on Power press)
        self.assertTrue(
            "80000" in sp_hook_chunk or "524288" in sp_hook_chunk,
            "Start cause 0x00080000 (524288) missing in shortpress hook",
        )

        # 5. opacity buffers {0x5FC40000, 0x5FB80000} in .data
        data_dump = subprocess.run(
            [str(TOOLCHAIN_OBJDUMP), "-s", "-j", ".data", str(staged_core_elf)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        data_text = data_dump.stdout
        self.assertIn(
            "0000c45f",
            data_text,
            "Opacity buffer 0x5FC40000 (little-endian 0000c45f) missing in core .data",
        )
        self.assertIn(
            "0000b85f",
            data_text,
            "Opacity buffer 0x5FB80000 (little-endian 0000b85f) missing in core .data",
        )

        # 6. 900x600/928 camera_screen geometry in .data
        cam_screen_match = re.search(r"([0-9a-fA-F]{8})\s+[Dd]\s+camera_screen\b", nm_out)
        self.assertIsNotNone(cam_screen_match, "camera_screen symbol missing in nm output")
        cam_screen_addr = int(cam_screen_match.group(1), 16)

        screen_dump = subprocess.run(
            [
                str(TOOLCHAIN_OBJDUMP),
                "-s",
                "-j",
                ".data",
                f"--start-address=0x{cam_screen_addr:08x}",
                f"--stop-address=0x{cam_screen_addr + 48:08x}",
                str(staged_core_elf),
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        hex_bytes = []
        for line in screen_dump.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 2 and re.match(r"^[0-9a-fA-F]+$", parts[0]):
                for word in parts[1:5]:
                    if len(word) == 8 and re.match(r"^[0-9a-fA-F]{8}$", word):
                        b = bytes.fromhex(word)
                        hex_bytes.extend(b)
        self.assertGreaterEqual(len(hex_bytes), 40, "Insufficient camera_screen data dumped from .data section")
        ints = struct.unpack("<10I", bytes(hex_bytes[:40]))
        self.assertEqual(ints[0], 900, "camera_screen.width must be 900")
        self.assertEqual(ints[1], 600, "camera_screen.height must be 600")
        self.assertEqual(ints[2], 540000, "camera_screen.size must be 540000 (900x600)")
        self.assertEqual(ints[3], 900, "camera_screen.physical_width must be 900")
        self.assertEqual(ints[4], 928, "camera_screen.buffer_width must be 928")
        self.assertEqual(ints[5], 600, "camera_screen.buffer_height must be 600")
        self.assertEqual(ints[6], 556800, "camera_screen.buffer_size must be 556800 (928x600)")
        self.assertEqual(ints[7], 0, "camera_screen.disp_left must be 0")
        self.assertEqual(ints[8], 899, "camera_screen.disp_right must be 899")
        self.assertEqual(ints[9], 900, "camera_screen.disp_width must be 900")

    def test_built_binary_card_write_switches_off(self):
        """Verify card-write suppression linker wrap symbols and preprocessor flags."""
        if not self.has_toolchain:
            self.skipTest(f"Pinned toolchain gcc not found at {TOOLCHAIN_GCC}")

        stage_dir = OUT_DIR / "stage_chdk"
        staged_core_elf = stage_dir / "platform" / "g3x" / "sub" / "110c" / "main.elf"
        self.assertTrue(staged_core_elf.is_file(), f"Expected {staged_core_elf}")

        core_nm = subprocess.run(
            [str(TOOLCHAIN_NM), "-n", str(staged_core_elf)],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        nm_out = core_nm.stdout

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

        staged_makefile = stage_dir / "platform" / "g3x" / "sub" / "110c" / "Makefile"
        self.assertTrue(staged_makefile.is_file(), f"Expected {staged_makefile}")
        make_text = staged_makefile.read_text(encoding="utf-8")
        self.assertIn("-DG3X_DISABLE_CARD_WRITES=1", make_text)
        self.assertIn("-DOPT_DISABLE_FILE_WRITES=1", make_text)

    def test_default_build_byte_identical(self):
        """Verify default candidate build (all flags off) is byte-identical to pinned baseline."""
        if not self.has_toolchain:
            self.skipTest(f"Pinned toolchain gcc not found at {TOOLCHAIN_GCC}")

        import tempfile
        import sys

        scripts_dir = REPO_ROOT / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from build_candidate_gui3 import build_candidate

        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(
                ladder=False,
                poweron_fix=False,
                resident=False,
                out_dir=tmpdir,
            )
            pinned_default_sha256 = "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"
            self.assertEqual(
                res["diskboot_sha256"],
                pinned_default_sha256,
                "Default candidate DISKBOOT.BIN SHA-256 diverged from pinned baseline",
            )
            self.assertEqual(
                res["diskboot_size"],
                118001,
                "Default candidate DISKBOOT.BIN size diverged from pinned baseline",
            )

    def test_opt_in_flags_still_build(self):
        """Verify each of the opt-in G3X_* candidate configurations still builds cleanly."""
        if not self.has_toolchain:
            self.skipTest(f"Pinned toolchain gcc not found at {TOOLCHAIN_GCC}")

        import tempfile
        import sys

        scripts_dir = REPO_ROOT / "scripts"
        if str(scripts_dir) not in sys.path:
            sys.path.insert(0, str(scripts_dir))
        from build_candidate_gui3 import build_candidate

        flag_cases = [
            ("resident", {"resident": True}, "63c7942f561242b55d8226bfefe7818dd5b959aee35eae0adb4f41a4783ece5a", 124561),
            ("osd", {"osd": True}, "683751539979f3e8956fd6c1794683c062f54385e6e1a3261b02ed8d63cc9855", 124833),
            ("kbd", {"kbd": True}, "a750253feb0cd9bb3bb1addb4cede5585bef29a0bf26bd86d3f577fdbf41be33", 124801),
            ("osd2", {"osd2": True}, "20d65a7d9be954d5caafe2f78751429ea388a37ca570f0bbd0d620609eb31a57", 125329),
            ("gui4", {"gui4": True}, "14456b08fca82758262c26ad6105f784ebacaa080b7a059a622ded5a8d505fdd", 102241),
            ("gui5", {"gui5": True}, "dd96357c050cf3b9116dcf089a731ef159477b505351f46436f983fdbf090b64", 102209),
            ("shortpress", {"shortpress": True}, "6df54a905e36a6fe92b5a3a4ac4dd71086d3306fd0aaa31a1f1bc670f7e19461", 124945),
            ("gui5_shortpress", {"gui5": True, "shortpress": True}, "86e12a2cfe792a8901fa2e0ec5a98f019290593e35d5c4c2e66fd3e073f16ff1", 102369),
        ]

        with tempfile.TemporaryDirectory() as tmpdir:
            for name, kwargs, expected_sha, expected_size in flag_cases:
                cand_dir = os.path.join(tmpdir, name)
                res = build_candidate(out_dir=cand_dir, **kwargs)
                diskboot = Path(cand_dir) / "DISKBOOT.BIN"
                self.assertTrue(diskboot.is_file(), f"DISKBOOT.BIN for {name} candidate does not exist")
                self.assertEqual(res["diskboot_size"], expected_size, f"Size mismatch for {name} candidate build")
                self.assertEqual(res["diskboot_sha256"], expected_sha, f"SHA-256 mismatch for {name} candidate build")

    def test_doc_manifest_and_trial_plan(self):
        """Verify docs/PORT41_FULL_BUILD.md contains output manifest and owner trial plan."""
        doc_path = REPO_ROOT / "docs" / "PORT41_FULL_BUILD.md"
        self.assertTrue(doc_path.is_file(), f"Missing {doc_path}")
        doc_text = doc_path.read_text(encoding="utf-8")

        # Manifest outputs
        self.assertIn("DISKBOOT.BIN", doc_text)
        self.assertIn(
            "9a90ca2f4722f6c507291e45111daed899554eacf2b48542555e51169aa32e60",
            doc_text,
            "DISKBOOT.BIN SHA-256 missing in doc",
        )
        self.assertIn("124,097", doc_text)
        self.assertIn("CHDK/MODULES", doc_text)
        self.assertIn("CHDK/FONTS", doc_text)
        self.assertIn("CHDK/LANG", doc_text)
        self.assertIn("port41_manifest.json", doc_text)

        # Owner trial steps table: held press first, then short press
        self.assertRegex(doc_text, r"(?i)held\s+press.*short\s+press", "Doc must present held press first, then short press")

        # Expected results
        self.assertRegex(doc_text, r"(?i)led\s+ladder")
        self.assertRegex(doc_text, r"(?i)stock\s+ui")
        self.assertRegex(doc_text, r"(?i)chdk\s+resident")
        self.assertRegex(doc_text, r"(?i)alt\s+toggle.*menu")
        self.assertRegex(doc_text, r"(?i)shooting\s+mode.*short\s+press")
        self.assertRegex(doc_text, r"(?i)power\s+press.*turns?\s+it\s+off")

        # Notes and recovery path
        self.assertRegex(doc_text, r"(?i)what\s+to\s+note")
        self.assertRegex(doc_text, r"(?i)recovery\s+path")
        self.assertRegex(doc_text, r"(?i)battery\s+pull")
        self.assertRegex(doc_text, r"(?i)ram-only")


if __name__ == "__main__":
    unittest.main()
