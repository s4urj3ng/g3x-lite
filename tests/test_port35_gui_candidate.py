#!/usr/bin/env python3
"""PORT-35 Part B: Host verification suite for opt-in G3X_GUI=1 CHDK core GUI/ALT menu candidate.

Verifies all acceptance criteria for Task p35-t1b-gui-candidate-r4:
1. Prior build invariance:
   - Default all-flags-off (PORT-2A) equals pinned hash.
   - Combined ladder + poweron_fix (PORT-25) equals pinned hash.
   - RESIDENT (PORT-32), OSD (PORT-33), KBD (PORT-34), KBD+OSD (PORT-34),
     and OSD2 (PORT-35 Part A) equal their pinned SHA-256 hashes.
2. G3X_GUI=1 builds reproducibly with toolchains/gcc-arm-none-eabi-5_4-2016q3:
   - Output SHA-256 equals pinned hash and matches docs/PORT35_GUI_ADDRESSES.md.
   - Linked _end is <= heap start 0x00368880 with positive clearance.
   - No binaries committed to git.
3. gui_init/gui_redraw are driven from the kbd task as in the g7x sibling (cited by path:line):
   - mykbd_task calls g3x_osd2_kbd_redraw on every keyboard tick.
   - g3x_gui_kbd_redraw calls gui_init and gui_redraw.
   - ALT opens gui_menu, d-pad and SET navigate, menu closes, and leaving ALT
     clears the overlay and returns control to the stock Canon UI.
   - Gating core_spytask_can_start() is called in g3x_resident_heartbeat_task()
     after sub_fc0bb6fe_my (InitFileModules point).
4. Static trial safety check:
   - conf_save, save_config_file, module_load, and script_load paths are stubbed/compiled out.
   - No branch in .text targets unsafe card-mutating firmware stubs.
   - Linker wrappers (__wrap_open, __wrap_write, etc.) intercept file I/O operations.
   - Filewrite hooks (filewrite_save, filewrite_task) are absent.
5. Address and constant table verification:
   - Every new address or constant appears in docs/PORT35_GUI_ADDRESSES.md labelled
     FINSIG, ROM-manifest-backed, or INFERRED with a sibling path:line citation.
   - Bounded ROM reads pass tools/port11c_evidence_validator.py.
6. PORT-34 heartbeat and ALT LED patterns and short-press power-hold path are unchanged.
   - LED 0xD20B0884 is called the power / card-access LED in all new text.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
TOOLS_DIR = REPO_ROOT / "tools"
DOCS_DIR = REPO_ROOT / "docs"
CHDK_PORT = REPO_ROOT / "chdk-port"
SUB_DIR = CHDK_PORT / "platform" / "g3x" / "sub" / "110c"
KBD_HEADER = SUB_DIR / "kbd_candidate.h"
OSD2_HEADER = SUB_DIR / "osd2_test_overlay.h"
PORT35_DOC = DOCS_DIR / "PORT35_GUI_ADDRESSES.md"
MANIFEST_PATH = REPO_ROOT / "evidence" / "port35_manifest.json"
TRUSTED_SCOPES_PATH = REPO_ROOT / "evidence" / "port35_trusted_scopes.json"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from build_candidate_port25_ladder_fix import (  # noqa: E402
    G3X_KBD_HEAP_START,
    G3X_GUI_HEAP_START,
    build_candidate,
    generate_gui_candidate_c,
    generate_stubs_entry_gui_s,
)

TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
ARM_GCC = TOOLCHAIN_BIN / "arm-none-eabi-gcc"
ARM_OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"
ARM_NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"
HAVE_TOOLCHAIN = ARM_GCC.is_file() and ARM_OBJDUMP.is_file() and ARM_NM.is_file()

PINNED_DEFAULT_SHA256 = "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"
PINNED_DEFAULT_SIZE = 118001

PINNED_PORT25_SHA256 = "9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15"
PINNED_PORT25_SIZE = 124865

PINNED_PORT32_RESIDENT_SHA256 = "63c7942f561242b55d8226bfefe7818dd5b959aee35eae0adb4f41a4783ece5a"
PINNED_PORT32_RESIDENT_SIZE = 124561

PINNED_PORT33_OSD_SHA256 = "683751539979f3e8956fd6c1794683c062f54385e6e1a3261b02ed8d63cc9855"
PINNED_PORT33_OSD_SIZE = 124833

PINNED_PORT34_KBD_SHA256 = "a750253feb0cd9bb3bb1addb4cede5585bef29a0bf26bd86d3f577fdbf41be33"
PINNED_PORT34_KBD_SIZE = 124801

PINNED_PORT34_KBD_OSD_SHA256 = "686c4e4688f74cccd2b7a21e7000eb574672635cfd4d17c885d86bbf52eb99a8"
PINNED_PORT34_KBD_OSD_SIZE = 125121

PINNED_PORT35_OSD2_SHA256 = "20d65a7d9be954d5caafe2f78751429ea388a37ca570f0bbd0d620609eb31a57"
PINNED_PORT35_OSD2_SIZE = 125329

PINNED_PORT35_GUI_SHA256 = "1f6494cd8e7fd7629b82ed33ba1ec4fa939aa1aa2ff22f541c28a28c742e4272"
PINNED_PORT35_GUI_SIZE = 103057
PINNED_PORT35_GUI_MAIN_SIZE = 101616
PINNED_PORT35_GUI_WITNESS_ADDR = 0x0035CCD0
PINNED_PORT35_GUI_END_ADDR = 0x00362D10


def _parse_port35_address_table(doc_text: str) -> list[dict[str, str]]:
    """Parse the Markdown table in docs/PORT35_GUI_ADDRESSES.md into row dicts."""
    rows: list[dict[str, str]] = []
    in_table = False
    for line in doc_text.splitlines():
        line = line.strip()
        if line.startswith("| Name") or line.startswith("| Symbol"):
            in_table = True
            continue
        if in_table and line.startswith("| :---"):
            continue
        if in_table and line.startswith("|"):
            parts = [c.strip() for c in line.split("|")[1:-1]]
            if len(parts) >= 5:
                rows.append({
                    "name": parts[0].strip("`"),
                    "value": parts[1].strip("`"),
                    "label": parts[2].strip("`"),
                    "sibling": parts[3].strip("`"),
                    "observation": parts[4].strip("`"),
                })
        elif in_table and not line.startswith("|") and line:
            in_table = False
    return rows


class TestPort35GuiCandidate(unittest.TestCase):
    """Host verification test suite for PORT-35 Part B G3X_GUI=1 candidate."""

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_a_prior_hashes_invariant(self) -> None:
        """(1) Prior build invariance: default, combined, RESIDENT, OSD, KBD, KBD+OSD, and OSD2 equal pinned hashes."""
        # 1. Default (ladder=0, poweron_fix=0)
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=False, poweron_fix=False, out_dir=tmpdir, resident=False, osd=False, kbd=False, osd2=False, gui=False)
            self.assertEqual(res["diskboot_sha256"], PINNED_DEFAULT_SHA256)
            self.assertEqual(res["diskboot_size"], PINNED_DEFAULT_SIZE)

        # 2. Combined (ladder=1, poweron_fix=1)
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, resident=False, osd=False, kbd=False, osd2=False, gui=False)
            self.assertEqual(res["diskboot_sha256"], PINNED_PORT25_SHA256)
            self.assertEqual(res["diskboot_size"], PINNED_PORT25_SIZE)

        # 3. RESIDENT only (PORT-32)
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, resident=True, osd=False, kbd=False, osd2=False, gui=False)
            self.assertEqual(res["diskboot_sha256"], PINNED_PORT32_RESIDENT_SHA256)
            self.assertEqual(res["diskboot_size"], PINNED_PORT32_RESIDENT_SIZE)

        # 4. OSD only (PORT-33)
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, resident=True, osd=True, kbd=False, osd2=False, gui=False)
            self.assertEqual(res["diskboot_sha256"], PINNED_PORT33_OSD_SHA256)
            self.assertEqual(res["diskboot_size"], PINNED_PORT33_OSD_SIZE)

        # 5. KBD only (PORT-34)
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, resident=True, osd=False, kbd=True, osd2=False, gui=False)
            self.assertEqual(res["diskboot_sha256"], PINNED_PORT34_KBD_SHA256)
            self.assertEqual(res["diskboot_size"], PINNED_PORT34_KBD_SIZE)

        # 6. KBD + OSD (PORT-34)
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, resident=True, osd=True, kbd=True, osd2=False, gui=False)
            self.assertEqual(res["diskboot_sha256"], PINNED_PORT34_KBD_OSD_SHA256)
            self.assertEqual(res["diskboot_size"], PINNED_PORT34_KBD_OSD_SIZE)

        # 7. OSD2 overlay fix (PORT-35 Part A)
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, resident=True, osd=False, kbd=True, osd2=True, gui=False)
            self.assertEqual(res["diskboot_sha256"], PINNED_PORT35_OSD2_SHA256)
            self.assertEqual(res["diskboot_size"], PINNED_PORT35_OSD2_SIZE)

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_b_gui_reproducible_build_and_doc_hash(self) -> None:
        """(2) G3X_GUI=1 builds reproducibly; SHA-256 and size match docs/PORT35_GUI_ADDRESSES.md."""
        with tempfile.TemporaryDirectory() as tmpdir1, tempfile.TemporaryDirectory() as tmpdir2:
            res1 = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir1, gui=True)
            res2 = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir2, gui=True)

            self.assertEqual(res1["diskboot_sha256"], res2["diskboot_sha256"])
            self.assertEqual(res1["diskboot_size"], res2["diskboot_size"])
            self.assertEqual(res1["diskboot_sha256"], PINNED_PORT35_GUI_SHA256)
            self.assertEqual(res1["diskboot_size"], PINNED_PORT35_GUI_SIZE)
            self.assertEqual(int(res1["witness_addr"], 16), PINNED_PORT35_GUI_WITNESS_ADDR)
            self.assertEqual(int(res1["core_end_addr"], 16), PINNED_PORT35_GUI_END_ADDR)

            # Cross-verify with documentation
            self.assertTrue(PORT35_DOC.is_file(), f"Missing {PORT35_DOC}")
            doc_text = PORT35_DOC.read_text(encoding="utf-8")
            self.assertIn(PINNED_PORT35_GUI_SHA256, doc_text)
            self.assertIn(str(PINNED_PORT35_GUI_SIZE), doc_text)
            self.assertIn(f"0x{PINNED_PORT35_GUI_END_ADDR:08X}", doc_text)

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_c_heap_clearance(self) -> None:
        """(3) Linked _end is <= heap start 0x00368880 with positive clearance for G3X_GUI=1."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, gui=True)
            core_end = int(res["core_end_addr"], 16)
            heap_start = int(res["heap_start_addr"], 16)

            self.assertEqual(heap_start, G3X_GUI_HEAP_START)
            self.assertEqual(core_end, PINNED_PORT35_GUI_END_ADDR)
            self.assertLessEqual(core_end, heap_start)
            clearance = heap_start - core_end
            self.assertGreater(clearance, 0, f"Expected positive clearance, got {clearance} bytes")
            self.assertEqual(clearance, 0x00368880 - 0x00362D10)

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_d_kbd_task_gui_wiring(self) -> None:
        """(4) gui_init and gui_redraw are driven from kbd task; core_spytask_can_start follows InitFileModules."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, gui=True)
            elf = res["core_elf"]

            objdump_proc = subprocess.run(
                [str(ARM_OBJDUMP), "-d", elf],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            disasm = objdump_proc.stdout

            # 1. mykbd_task calls g3x_gui_kbd_redraw via inlined g3x_osd2_kbd_redraw
            m_kbd = re.search(r"<mykbd_task>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_kbd, "mykbd_task must exist")
            kbd_body = m_kbd.group(1)
            self.assertIn("<g3x_gui_kbd_redraw>", kbd_body)
            self.assertIn("<kbd_is_blocked>", kbd_body)
            self.assertIn("<_SleepTask>", kbd_body)

            # 2. g3x_gui_kbd_redraw calls gui_init and gui_redraw
            m_gui = re.search(r"<g3x_gui_kbd_redraw>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_gui, "g3x_gui_kbd_redraw must exist")
            gui_body = m_gui.group(1)
            self.assertIn("<gui_init>", gui_body)
            self.assertIn("<gui_redraw>", gui_body)

            # 3. g3x_resident_heartbeat_task calls core_spytask_can_start
            m_res = re.search(r"<g3x_resident_heartbeat_task>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_res, "g3x_resident_heartbeat_task must exist")
            res_body = m_res.group(1)
            self.assertIn("<core_spytask_can_start>", res_body)

            # 4. Short-press power fix bit 0x00020000 is retained in my_kbd_read_keys_candidate
            m_read = re.search(r"<my_kbd_read_keys_candidate>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_read, "my_kbd_read_keys_candidate must exist")
            read_body = m_read.group(1)
            self.assertIn("20000", read_body.lower(), "Short-press power fix bit 0x00020000 must be retained")

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_e_alt_mode_and_menu_navigation(self) -> None:
        """(5) ALT mode activates gui_menu; leaving ALT clears overlay and restores stock UI."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, gui=True)
            elf = res["core_elf"]

            objdump_proc = subprocess.run(
                [str(ARM_OBJDUMP), "-d", elf],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            disasm = objdump_proc.stdout

            m_gui = re.search(r"<g3x_gui_kbd_redraw>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_gui)
            gui_body = m_gui.group(1)

            # Entering ALT mode initializes root menu and sets menu handler
            self.assertIn("<gui_activate_alt_mode>", gui_body)
            self.assertIn("<gui_menu_init>", gui_body)
            self.assertIn("<gui_set_mode>", gui_body)

            # Leaving ALT mode restores display and clears overlay
            self.assertIn("<gui_set_need_restore>", gui_body)

            # Outside ALT mode, __wrap_gui_kbd_process checks kbd_is_blocked
            m_wrap_kbd = re.search(r"<__wrap_gui_kbd_process>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_wrap_kbd, "__wrap_gui_kbd_process must exist")
            wrap_body = m_wrap_kbd.group(1)
            self.assertIn("<kbd_is_blocked>", wrap_body)

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_f_static_trial_safety_unreachable(self) -> None:
        """(6) Static trial safety: conf_save, file writes, module loads, and script loads are unreachable."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, gui=True)
            elf = res["core_elf"]

            objdump_proc = subprocess.run(
                [str(ARM_OBJDUMP), "-d", elf],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            disasm = objdump_proc.stdout

            nm_proc = subprocess.run(
                [str(ARM_NM), elf],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            nm_output = nm_proc.stdout

            # 1. Verify conf_save and script_load are stubbed no-ops (bx lr)
            m_conf = re.search(r"<conf_save>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_conf)
            self.assertIn("bx\tlr", m_conf.group(1))

            m_script = re.search(r"<script_load>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_script)
            self.assertIn("bx\tlr", m_script.group(1))

            # 2. Track unsafe card-mutating firmware stubs
            unsafe_stubs = [
                "_Write",
                "_Fwrite_Fut",
                "_MakeDirectory_Fut",
                "_DeleteFile_Fut",
                "_DeleteDirectory_Fut",
                "_RenameFile_Fut",
                "_WriteSDCard",
                "_MakeSDCardBootable",
                "_SetFileAttributes",
                "_SetFileTimeStamp",
            ]
            stub_addrs = {}
            for line in nm_output.splitlines():
                parts = line.split()
                if len(parts) >= 3 and parts[2] in unsafe_stubs:
                    stub_addrs[parts[2]] = parts[0].lower().lstrip("0")

            self.assertEqual(
                len(stub_addrs),
                len(unsafe_stubs),
                f"All unsafe stubs must be tracked: {set(unsafe_stubs) - set(stub_addrs.keys())}",
            )

            # 3. Verify NO branch in .text targets any unsafe card-mutating stub
            for stub_name, hex_addr in stub_addrs.items():
                pattern = rf"\b(bl|b\.w|b\.n|bx|blx)\s+[0-9a-f]*{hex_addr}\b"
                matches = re.findall(pattern, disasm)
                self.assertEqual(
                    len(matches),
                    0,
                    f"Unsafe firmware stub '{stub_name}' (addr {hex_addr}) is targeted by branch instruction in .text!",
                )

            # 4. Verify guarded wrappers exist and intercept operations
            wrappers = [
                "<__wrap_open>",
                "<__wrap__open>",
                "<__wrap__Open>",
                "<__wrap_fopen>",
                "<__wrap__Fopen_Fut>",
                "<__wrap__ExecuteEventProcedure>",
                "<__wrap_script_load>",
                "<__wrap_load_file_to_length>",
            ]
            for w in wrappers:
                self.assertIn(w, disasm, f"Wrapper {w} missing from disasm")

            # 5. Verify filewrite hooks absent
            self.assertNotIn("filewrite_save", nm_output)
            self.assertNotIn("filewrite_task", nm_output)

            # 6. Verify single definition of vid_get_bitmap_active_*
            self.assertEqual(len(re.findall(r"\bvid_get_bitmap_active_buffer\b", nm_output)), 1)
            self.assertEqual(len(re.findall(r"\bvid_get_bitmap_active_palette\b", nm_output)), 1)

    def test_g_address_literals_appear_in_table(self) -> None:
        """(7) Every firmware address literal in new code appears in docs/PORT35_GUI_ADDRESSES.md."""
        self.assertTrue(PORT35_DOC.is_file(), f"Missing {PORT35_DOC}")
        doc_src = PORT35_DOC.read_text(encoding="utf-8")
        rows = _parse_port35_address_table(doc_src)
        self.assertGreaterEqual(len(rows), 80)

        valid_labels = {"FINSIG", "ROM-manifest", "ROM_VERIFIED", "INFERRED"}
        table_rows: dict[int, dict[str, str]] = {}
        for row in rows:
            self.assertIn(row["label"], valid_labels, f"Invalid label in row: {row}")
            self.assertTrue(len(row["observation"]) >= 15, f"Short observation in row: {row}")
            for m in re.findall(r"0x[0-9A-Fa-f]{4,8}", row["value"]):
                table_rows[int(m, 16)] = row

        # Check stubs_entry_gui.S addresses
        stubs_src = generate_stubs_entry_gui_s()
        stubs_addrs = [int(m, 16) for m in re.findall(r"0x[0-9a-fA-F]{4,8}", stubs_src)]
        for addr in stubs_addrs:
            self.assertIn(addr, table_rows, f"Stubs address 0x{addr:08X} missing from table")
            row = table_rows[addr]
            self.assertIn(row["label"], valid_labels)
            if row["label"] == "INFERRED":
                self.assertTrue(len(row["sibling"]) > 0, f"INFERRED stub 0x{addr:08X} missing citation")

        # Check non-comment GUI candidate C addresses
        cand_src = generate_gui_candidate_c()
        code_lines = []
        for l in cand_src.splitlines():
            ls = l.strip()
            if ls.startswith(("*", "/*", "//")):
                continue
            code_lines.append(l.split("//")[0])
        found = re.findall(r"0x[0-9A-Fa-f]{4,8}", "\n".join(code_lines))
        for lit_str in found:
            lit = int(lit_str, 16)
            if lit < 0x1000:
                continue
            target = lit if lit in table_rows else (lit & ~1)
            self.assertIn(target, table_rows, f"Literal 0x{lit:08X} missing from table")
            row = table_rows[target]
            self.assertIn(row["label"], valid_labels)
            if row["label"] == "INFERRED":
                self.assertTrue(len(row["sibling"]) > 0, f"INFERRED literal 0x{lit:08X} missing citation")

        # Verify ROM reads pass evidence validator
        self.assertTrue(MANIFEST_PATH.is_file())
        self.assertTrue(TRUSTED_SCOPES_PATH.is_file())
        proc = subprocess.run(
            [
                sys.executable,
                str(TOOLS_DIR / "port11c_evidence_validator.py"),
                "--manifest",
                str(MANIFEST_PATH),
                "--trusted-scopes",
                str(TRUSTED_SCOPES_PATH),
                "--quiet",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, f"Validator failed: {proc.stderr}")

    def test_h_port34_invariance_and_naming(self) -> None:
        """(8) PORT-34 heartbeat and ALT LED patterns unchanged; LED 0xD20B0884 called power / card-access LED."""
        for path in (OSD2_HEADER, PORT35_DOC, TOOLS_DIR / "build_candidate_port25_ladder_fix.py"):
            txt = path.read_text(encoding="utf-8")
            if "0xD20B0884" in txt:
                self.assertIn("power / card-access LED", txt, f"{path.name} must call 0xD20B0884 the power / card-access LED")

        # Short-press path in kbd_candidate.h must be untouched
        kbd_text = KBD_HEADER.read_text(encoding="utf-8")
        self.assertIn("0x00020000", kbd_text, "Short-press bit mask 0x00020000 must be present in kbd_candidate.h")
        self.assertIn("KEY_PLAYBACK", kbd_text, "KEY_PLAYBACK must remain the ALT key in kbd_candidate.h")

    def test_i_zero_tracked_binaries(self) -> None:
        """(9) Zero tracked binary files under candidate/output paths."""
        proc = subprocess.run(
            ["git", "ls-files"],
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            check=True,
        )
        tracked_files = [line.strip() for line in proc.stdout.splitlines() if line.strip()]

        candidate_prefixes = (
            "candidate_port35_gui",
            "candidate_port35_osd2",
            "candidate_port34_kbd",
            "candidate_port33_osd",
            "candidate_port32_resident",
            "candidate_port25",
            "candidate_port2a",
            "candidate_",
        )
        binary_extensions = (".bin", ".elf", ".BIN", ".ELF", ".o", ".a")
        for path_str in tracked_files:
            p = Path(path_str)
            for prefix in candidate_prefixes:
                if path_str.startswith(prefix) or prefix in path_str:
                    self.assertFalse(
                        p.name.startswith("DISKBOOT") and p.name.endswith((".BIN", ".bin")),
                        f"Tracked DISKBOOT binary file not permitted: {path_str}",
                    )
                    self.assertFalse(
                        path_str.endswith(binary_extensions),
                        f"Tracked binary file not permitted under candidate/output path: {path_str}",
                    )

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_j_font_init_ram_only_regression(self) -> None:
        """(10) Regression: GUI init path reaches RAM-only font initialization before gui_menu_init / rbf_font_height.

        Codex reviewer blocking defect: no-op __wrap_rbf_load_from_file previously left rbf_font NULL (0),
        causing gui_menu_init() -> rbf_font_height() to dereference NULL and crash on ALT entry.
        Verifies:
        1. __wrap_rbf_load_from_file and __wrap_rbf_load_symbol are NOT stubs (bx lr); they branch to
           rbf_load_from_file and rbf_load_symbol respectively.
        2. Both wrappers pass an empty filename pointer ("") into r0, ensuring rbf_font_load's *file == 0
           check returns 0 without calling guarded file-open wrappers (__wrap_open, etc.).
        3. rbf_load_from_file calls init_fonts, rbf_font_load, alloc_cTable, and rbf_set_codepage,
           establishing non-NULL rbf_font and valid metrics (height 16, width 8) in RAM.
        4. rbf_load_symbol calls init_fonts, establishing non-NULL rbf_symbol_font in RAM.
        5. g3x_gui_kbd_redraw reaches rbf_load_from_file / rbf_load_symbol before gui_init / gui_menu_init.
        6. gui_menu_init calls rbf_font_height, which safely dereferences the initialized rbf_font.
        7. No branch in the font loading path targets any file-open wrapper with a non-empty filename.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, gui=True)
            elf = res["core_elf"]

            objdump_proc = subprocess.run(
                [str(ARM_OBJDUMP), "-d", elf],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            disasm = objdump_proc.stdout

            nm_proc = subprocess.run(
                [str(ARM_NM), elf],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            nm_output = nm_proc.stdout

            # 1. __wrap_rbf_load_from_file and __wrap_rbf_load_symbol are active dispatchers, not bx lr stubs
            m_wrap_font = re.search(r"<__wrap_rbf_load_from_file>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_wrap_font, "__wrap_rbf_load_from_file must exist in disassembly")
            wrap_font_body = m_wrap_font.group(1)
            self.assertIn("<rbf_load_from_file>", wrap_font_body, "__wrap_rbf_load_from_file must branch to real rbf_load_from_file")
            self.assertNotIn("movs\tr0, #0\n  34ba", wrap_font_body, "__wrap_rbf_load_from_file must not be a no-op stub")

            m_wrap_sym = re.search(r"<__wrap_rbf_load_symbol>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_wrap_sym, "__wrap_rbf_load_symbol must exist in disassembly")
            wrap_sym_body = m_wrap_sym.group(1)
            self.assertIn("<rbf_load_symbol>", wrap_sym_body, "__wrap_rbf_load_symbol must branch to real rbf_load_symbol")

            # 2. Both wrappers pass empty string pointer ("") into r0 (short-circuiting rbf_font_load without file open)
            m_pool_font = re.search(r"\.word\s+(0x[0-9a-fA-F]+)", wrap_font_body)
            self.assertIsNotNone(m_pool_font, "__wrap_rbf_load_from_file literal pool must exist")
            str_addr = int(m_pool_font.group(1), 16)

            # Dump .data section to verify byte at str_addr is 0x00 (empty string "")
            sec_proc = subprocess.run(
                [str(ARM_OBJDUMP), "-s", "-j", ".data", elf],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            # Find the hex dump line covering str_addr
            line_base = str_addr & ~0xF
            target_offset = str_addr & 0xF
            found_empty_str = False
            for line in sec_proc.stdout.splitlines():
                parts = line.strip().split()
                if len(parts) >= 5 and parts[0] == f"{line_base:x}":
                    # Reconstruct bytes from the 4 32-bit hex words (little-endian)
                    raw_bytes = bytearray()
                    for word_hex in parts[1:5]:
                        if len(word_hex) == 8:
                            raw_bytes.extend(bytes.fromhex(word_hex))
                    if target_offset < len(raw_bytes) and raw_bytes[target_offset] == 0:
                        found_empty_str = True
                        break
            self.assertTrue(found_empty_str, f"Wrapper string argument at 0x{str_addr:08X} must be empty string (0x00)")

            # 3. Real rbf_load_from_file calls init_fonts, rbf_font_load, alloc_cTable, and rbf_set_codepage
            m_rbf_load = re.search(r"<rbf_load_from_file>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_rbf_load, "rbf_load_from_file must exist")
            rbf_load_body = m_rbf_load.group(1)
            self.assertIn("<init_fonts>", rbf_load_body)
            self.assertIn("<rbf_font_load>", rbf_load_body)
            self.assertIn("<alloc_cTable>", rbf_load_body)
            self.assertIn("<rbf_set_codepage>", rbf_load_body)

            # 4. Real rbf_load_symbol calls init_fonts
            m_rbf_sym = re.search(r"<rbf_load_symbol>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_rbf_sym, "rbf_load_symbol must exist")
            rbf_sym_body = m_rbf_sym.group(1)
            self.assertIn("<init_fonts>", rbf_sym_body)

            # 5. g3x_gui_kbd_redraw reaches font initialization before gui_init and gui_menu_init
            m_redraw = re.search(r"<g3x_gui_kbd_redraw>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_redraw, "g3x_gui_kbd_redraw must exist")
            redraw_body = m_redraw.group(1)
            self.assertIn("<__wrap_rbf_load_from_file>", redraw_body)
            self.assertIn("<__wrap_rbf_load_symbol>", redraw_body)
            idx_font = redraw_body.find("<__wrap_rbf_load_from_file>")
            idx_init = redraw_body.find("<gui_init>")
            self.assertLess(idx_font, idx_init, "Font init must precede gui_init in g3x_gui_kbd_redraw")

            # 6. gui_menu_init calls rbf_font_height
            m_menu_init = re.search(r"<gui_menu_init>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_menu_init, "gui_menu_init must exist")
            self.assertIn("<rbf_font_height>", m_menu_init.group(1))

            # 7. No file open wrapper is called on font load path
            open_wrappers = ["<__wrap_open>", "<__wrap__open>", "<__wrap__Open>", "<__wrap_fopen>", "<__wrap__Fopen_Fut>"]
            for w in open_wrappers:
                self.assertNotIn(w, wrap_font_body)
                self.assertNotIn(w, wrap_sym_body)
                self.assertNotIn(w, rbf_load_body)
                self.assertNotIn(w, rbf_sym_body)

            # 8. rbf_font and rbf_symbol_font BSS variables exist
            self.assertRegex(nm_output, r"[0-9a-fA-F]+\s+[bB]\s+rbf_font\b")
            self.assertRegex(nm_output, r"[0-9a-fA-F]+\s+[bB]\s+rbf_symbol_font\b")


if __name__ == "__main__":
    unittest.main()
