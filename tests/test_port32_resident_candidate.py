#!/usr/bin/env python3
"""PORT-32 T2+T3: Host test suite for opt-in G3X_RESIDENT=1 heartbeat candidate.

Verifies:
(a) With G3X_RESIDENT off, DISKBOOT.BIN SHA-256 equals the pinned PORT-25 combined hash.
(b) PORT-24/25 outputs and ladder codes (11..44) are unchanged.
(c) Every firmware address in the resident code appears in a validated
    PORT-24/25/27/29/30/31 manifest, with manifest file and evidence ID cited in code comments.
(d) Two flag-on (G3X_RESIDENT=1) builds with the pinned toolchain
    (toolchains/gcc-arm-none-eabi-5_4-2016q3) produce the exact same SHA-256,
    matching docs/PORT32_RESIDENT_CANDIDATE.md, and disassembly confirms:
    - Heap start raised to 0x00368680 under the flag only.
    - CreateTask (0xBFE14A3D, FINSIG NHSTUB) called after ladder Code 44 at the sub_fc0d0126 handoff.
    - Explicit cited stack size r2 = 0x2000 (never 0) and priority r1 = 0x19 (25 >= 23/24/25).
    - ~1 Hz double-short-blink LED heartbeat (100/100/100/700 ms, unit labelled INFERRED)
      using PORT-25 LED register 0xD20B0884 (ON 0x004D0002, OFF 0x004C0003) and SleepTask (0xFC31BF84).
(e) docs/PORT32_RESIDENT_CANDIDATE.md assumptions table structure and zero tracked binaries.
(f) Spawn sequence saves and restores r0-r3 and keeps sp balanced around CreateTask before
    sub_fc0d0126 handoff, and no inline sp write exists inside any C function body.
"""

from __future__ import annotations

import hashlib
import json
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
EVIDENCE_DIR = REPO_ROOT / "evidence"
AGENTBRIDGE_DOCS_DIR = DOCS_DIR / "agentbridge"
CHDK_PORT = REPO_ROOT / "chdk-port"
SUB_DIR = CHDK_PORT / "platform" / "g3x" / "sub" / "110c"

TOOLCHAIN_BIN = REPO_ROOT / "toolchains" / "gcc-arm-none-eabi-5_4-2016q3" / "bin"
ARM_GCC = TOOLCHAIN_BIN / "arm-none-eabi-gcc"
ARM_OBJDUMP = TOOLCHAIN_BIN / "arm-none-eabi-objdump"
ARM_NM = TOOLCHAIN_BIN / "arm-none-eabi-nm"

if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from build_candidate_port2a import extract_symbol_addr_from_nm  # noqa: E402
from build_candidate_port25_ladder_fix import (  # noqa: E402
    BOOT_PROTOTYPE_LADDER_C,
    BOOT_PROTOTYPE_RESIDENT_C,
    G3X_RESIDENT_CREATETASK_ADDR,
    G3X_RESIDENT_HANDOFF_ADDR,
    G3X_RESIDENT_HEAP_START,
    G3X_RESIDENT_PRIORITY,
    G3X_RESIDENT_SLEEPTASK_ADDR,
    G3X_RESIDENT_SLEEPTASK_VENEER,
    G3X_RESIDENT_STACK_SIZE,
    build_candidate,
)

PINNED_DEFAULT_SHA256 = "9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136"
PINNED_DEFAULT_SIZE = 118001

PINNED_POWERON_FIX_SHA256 = "faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056"
PINNED_POWERON_FIX_SIZE = 118001

PINNED_PORT25_LADDER_ONLY_SHA256 = "45da469f3eb46c4d2aff77a032e5c8bb4eedf8ec8846526853d716d05d2b2f4e"
PINNED_PORT25_LADDER_ONLY_SIZE = 126081

PINNED_PORT25_COMBINED_SHA256 = "9ba62067c17d654a3b8995fc6e8c26176321154054a138a465ca66f9ff763a15"
PINNED_PORT25_COMBINED_SIZE = 124865

PINNED_PORT32_RESIDENT_SHA256 = "63c7942f561242b55d8226bfefe7818dd5b959aee35eae0adb4f41a4783ece5a"
PINNED_PORT32_RESIDENT_SIZE = 124561
PINNED_PORT32_RESIDENT_MAIN_SIZE = 123120
PINNED_PORT32_RESIDENT_END_ADDR = 0x00368550

EXPECTED_LADDER_CODES = [
    11, 12, 13, 14, 15,
    21, 22, 23, 24, 25, 26, 28, 29,
    31, 32, 33, 34, 35,
    41, 42, 43, 44,
]


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def have_pinned_toolchain() -> bool:
    if not (ARM_GCC.is_file() and os.access(ARM_GCC, os.X_OK)):
        return False
    if not (ARM_OBJDUMP.is_file() and os.access(ARM_OBJDUMP, os.X_OK)):
        return False
    try:
        res = subprocess.run([str(ARM_GCC), "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=5)
        return res.returncode == 0
    except Exception:
        return False


HAVE_TOOLCHAIN = have_pinned_toolchain()


class TestPort32ResidentCandidate(unittest.TestCase):
    """Host test suite for PORT-32 opt-in G3X_RESIDENT=1 candidate."""

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_a_flag_off_combined_equals_pinned_port25_hash(self) -> None:
        """(a) With G3X_RESIDENT off, DISKBOOT.BIN SHA-256 equals pinned PORT-25 combined hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, resident=False)
            self.assertFalse(res["resident"])
            self.assertEqual(res["diskboot_sha256"], PINNED_PORT25_COMBINED_SHA256)
            self.assertEqual(res["diskboot_size"], PINNED_PORT25_COMBINED_SIZE)
            self.assertEqual(sha256_file(res["diskboot_bin"]), PINNED_PORT25_COMBINED_SHA256)

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_b_port24_port25_outputs_and_ladder_codes_unchanged(self) -> None:
        """(b) PORT-24/25 outputs (--default, --poweron-fix, --ladder) and ladder codes (11..44) are unchanged."""
        with tempfile.TemporaryDirectory() as tmp_def:
            res_def = build_candidate(ladder=False, poweron_fix=False, out_dir=tmp_def, resident=False)
            self.assertEqual(res_def["diskboot_sha256"], PINNED_DEFAULT_SHA256)
            self.assertEqual(res_def["diskboot_size"], PINNED_DEFAULT_SIZE)

        with tempfile.TemporaryDirectory() as tmp_pwr:
            res_pwr = build_candidate(ladder=False, poweron_fix=True, out_dir=tmp_pwr, resident=False)
            self.assertEqual(res_pwr["diskboot_sha256"], PINNED_POWERON_FIX_SHA256)
            self.assertEqual(res_pwr["diskboot_size"], PINNED_POWERON_FIX_SIZE)

        with tempfile.TemporaryDirectory() as tmp_lad:
            res_lad = build_candidate(ladder=True, poweron_fix=False, out_dir=tmp_lad, resident=False)
            self.assertEqual(res_lad["diskboot_sha256"], PINNED_PORT25_LADDER_ONLY_SHA256)
            self.assertEqual(res_lad["diskboot_size"], PINNED_PORT25_LADDER_ONLY_SIZE)

        # Verify all ladder codes 11..44 remain intact in led_breadcrumb.h and generated sources
        hdr_text = (SUB_DIR / "led_breadcrumb.h").read_text(encoding="utf-8")
        for code in EXPECTED_LADDER_CODES:
            macro = f"CORE_LADDER_PULSE_{code}"
            self.assertIn(f"#define {macro}", hdr_text, f"Missing {macro} in led_breadcrumb.h")
            self.assertIn(macro, BOOT_PROTOTYPE_LADDER_C, f"Missing {macro} in ladder C source")
            self.assertIn(macro, BOOT_PROTOTYPE_RESIDENT_C, f"Missing {macro} in resident C source")

    def test_c_every_firmware_address_in_validated_manifests_and_cited(self) -> None:
        """(c) Every firmware address in resident code appears in a validated PORT-24/25/27/29/30/31 manifest."""
        manifest_files = {
            "docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json": AGENTBRIDGE_DOCS_DIR / "PORT24_EVIDENCE_MANIFEST.json",
            "docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json": AGENTBRIDGE_DOCS_DIR / "PORT25_EVIDENCE_MANIFEST.json",
            "docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json": AGENTBRIDGE_DOCS_DIR / "PORT27_EVIDENCE_MANIFEST.json",
            "evidence/port29_manifest.json": EVIDENCE_DIR / "port29_manifest.json",
            "evidence/port30_manifest.json": EVIDENCE_DIR / "port30_manifest.json",
            "evidence/port31_manifest.json": EVIDENCE_DIR / "port31_manifest.json",
        }
        loaded_manifests: dict[str, dict] = {}
        rom_ranges: list[tuple[int, int, str, str]] = []
        manifest_text_by_rel: dict[str, str] = {}

        for rel, path in manifest_files.items():
            self.assertTrue(path.is_file(), f"Missing validated manifest {rel}")
            raw_text = path.read_text(encoding="utf-8")
            manifest_text_by_rel[rel] = raw_text
            data = json.loads(raw_text)
            loaded_manifests[rel] = data
            entries = data.get("evidence", []) + data.get("evidence_entries", [])
            for entry in entries:
                eid = entry.get("id") or entry.get("evidence_id") or ""
                if "rom_window" in entry:
                    start = int(entry["rom_window"]["start"], 16)
                    end = int(entry["rom_window"]["end"], 16)
                    rom_ranges.append((start, end, rel, eid))
                elif "start" in entry and "end" in entry:
                    start = int(entry["start"], 16)
                    end = int(entry["end"], 16)
                    rom_ranges.append((start, end, rel, eid))
                elif "start_address" in entry and "end_address" in entry:
                    start = int(entry["start_address"], 16)
                    end = int(entry["end_address"], 16)
                    rom_ranges.append((start, end, rel, eid))

        # Extract the G3X_RESIDENT block from led_breadcrumb.h and resident additions in BOOT_PROTOTYPE_RESIDENT_C
        hdr_text = (SUB_DIR / "led_breadcrumb.h").read_text(encoding="utf-8")
        res_split = hdr_text.split("#if defined(G3X_RESIDENT) && (G3X_RESIDENT == 1)")
        self.assertEqual(len(res_split), 2, "Expected exactly one G3X_RESIDENT guard block in led_breadcrumb.h")
        resident_hdr_block = res_split[1]

        # Expected firmware addresses used in the resident code and their manifest provenance
        expected_addresses = {
            0x003489B4: ("docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json", "PORT27-ROM-HEAP-SETUP"),
            0x00368680: ("docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json", "PORT27-ROM-HEAP-SETUP"),
            0xBFE14A3D: ("docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json", "PORT27-ROM-CREATETASK-VENEER"),
            0xBFE14A3C: ("evidence/port31_manifest.json", "PORT29-ROM-CREATETASK"),
            0xBFE14AF1: ("evidence/port31_manifest.json", "PORT29-ROM-CREATETASK"),
            0xFCEF3488: ("evidence/port31_manifest.json", "PORT29-ROM-CREATETASK"),
            0xFC0D0126: ("docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json", "PORT27-ROM-FIRMWARE-CONT"),
            0xFC31BF84: ("docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json", "PORT27-ROM-SLEEPTASK-VENEER"),
            0xFC31BF8F: ("docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json", "PORT27-ROM-SLEEPTASK-VENEER"),
            0xBFE14968: ("evidence/port31_manifest.json", "PORT30-ROM-SLEEPTASK"),
            0xBFE14969: ("docs/agentbridge/PORT27_EVIDENCE_MANIFEST.json", "PORT27-ROM-SLEEPTASK-VENEER"),
            0xFCEF33B4: ("evidence/port31_manifest.json", "PORT30-ROM-SLEEPTASK"),
            0xD20B0884: ("docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json", "PORT25-ROM-GPIO-WRITE-MMIO"),
            0x004D0002: ("docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json", "PORT25-ROM-GPIO-WRITE-MMIO"),
            0x004C0003: ("docs/agentbridge/PORT25_EVIDENCE_MANIFEST.json", "PORT25-ROM-GPIO-WRITE-MMIO"),
        }

        # Check that all 8-digit hex literals in resident_hdr_block are in expected_addresses or covered by a ROM range
        found_hex = set(re.findall(r"0x[0-9a-fA-F]{8}", resident_hdr_block))
        self.assertTrue(found_hex, "Expected hex literals in resident_hdr_block")
        for hx in found_hex:
            val = int(hx, 16)
            if val >= 0xFC000000:
                covered = any(start <= val <= end for start, end, _, _ in rom_ranges)
                self.assertTrue(
                    covered,
                    f"ROM address 0x{val:08X} in resident code is not covered by any validated manifest ROM window",
                )
            else:
                self.assertIn(
                    val,
                    expected_addresses,
                    f"Non-ROM 32-bit hex constant 0x{val:08X} in resident code is not in validated expected_addresses",
                )

        # Verify code comments cite manifest file and evidence ID for each address
        combined_resident_code = resident_hdr_block + "\n" + BOOT_PROTOTYPE_RESIDENT_C
        for addr, (manifest_rel, evidence_id) in expected_addresses.items():
            self.assertIn(
                manifest_rel,
                combined_resident_code,
                f"Resident code comments must cite manifest {manifest_rel} for 0x{addr:08X}",
            )
            self.assertIn(
                evidence_id,
                combined_resident_code,
                f"Resident code comments must cite evidence ID {evidence_id} for 0x{addr:08X}",
            )
            self.assertIn(
                evidence_id,
                manifest_text_by_rel[manifest_rel],
                f"Evidence ID {evidence_id} not found in {manifest_rel}",
            )

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_d_flag_on_reproducibility_doc_match_and_disassembly(self) -> None:
        """(d) Two flag-on builds produce identical hash matching doc, and disassembly verifies resident contract."""
        doc_path = DOCS_DIR / "PORT32_RESIDENT_CANDIDATE.md"
        self.assertTrue(doc_path.is_file(), f"Missing {doc_path}")
        doc_text = doc_path.read_text(encoding="utf-8")

        with tempfile.TemporaryDirectory() as tmp1, tempfile.TemporaryDirectory() as tmp2:
            res1 = build_candidate(ladder=True, poweron_fix=True, out_dir=tmp1, resident=True)
            res2 = build_candidate(ladder=True, poweron_fix=True, out_dir=tmp2, resident=True)

            self.assertTrue(res1["resident"])
            self.assertTrue(res2["resident"])
            self.assertEqual(res1["diskboot_sha256"], res2["diskboot_sha256"])
            self.assertEqual(res1["diskboot_size"], res2["diskboot_size"])
            self.assertEqual(res1["diskboot_sha256"], PINNED_PORT32_RESIDENT_SHA256)
            self.assertEqual(res1["diskboot_size"], PINNED_PORT32_RESIDENT_SIZE)
            self.assertEqual(res1["core_end_addr"], f"0x{PINNED_PORT32_RESIDENT_END_ADDR:08X}")
            self.assertEqual(res1["heap_start_addr"], "0x00368680")

            # Hash, loaded size, linked _end, heap start, and toolchain must appear in docs/PORT32_RESIDENT_CANDIDATE.md
            self.assertIn(res1["diskboot_sha256"], doc_text)
            self.assertIn("123,120", doc_text)
            self.assertIn(res1["core_end_addr"], doc_text)
            self.assertIn(res1["heap_start_addr"], doc_text)
            self.assertIn("toolchains/gcc-arm-none-eabi-5_4-2016q3", doc_text)

            # Trial plan must also record the updated flag-on DISKBOOT.BIN SHA-256
            trial_plan_path = DOCS_DIR / "PORT32_TRIAL_PLAN.md"
            self.assertTrue(trial_plan_path.is_file(), f"Missing {trial_plan_path}")
            self.assertIn(res1["diskboot_sha256"], trial_plan_path.read_text(encoding="utf-8"))

            # Disassemble candidate_main.elf to verify resident implementation details
            proc = subprocess.run(
                [str(ARM_OBJDUMP), "-d", res1["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            disasm = proc.stdout

            # 1. Heap start 0x00368680 loaded in sub_fc05b3c8_my
            self.assertIn("00368680", disasm, "Raised heap start 0x00368680 must appear in disassembly")
            self.assertEqual(G3X_RESIDENT_HEAP_START, 0x00368680)

            # 2. Extract task_Startup_my and verify CreateTask 0xFCEF3488 called at sub_fc0d0126 handoff
            m_startup = re.search(
                r"<task_Startup_my>:(.*?)(?:\n\n|\Z)",
                disasm,
                re.DOTALL,
            )
            self.assertIsNotNone(m_startup, "task_Startup_my not found in candidate_main.elf disassembly")
            startup_body = m_startup.group(1)

            # Verify explicit stack size r2 = 0x2000 (8192, never 0) and priority r1 = 0x19 (25)
            self.assertEqual(G3X_RESIDENT_STACK_SIZE, 0x2000)
            self.assertNotEqual(G3X_RESIDENT_STACK_SIZE, 0)
            self.assertEqual(G3X_RESIDENT_PRIORITY, 0x19)
            self.assertGreaterEqual(G3X_RESIDENT_PRIORITY, 23)  # No higher urgency than task_PhySw=23, task_Startup=25
            self.assertIn("#8192", startup_body, "Expected mov.w r2, #8192 (0x2000) in task_Startup_my")
            self.assertIn("movs\tr1, #25", startup_body, "Expected movs r1, #25 (0x19) in task_Startup_my")
            self.assertIn("blx\tr4", startup_body, "Expected blx r4 (CreateTask) in task_Startup_my")
            self.assertIn("<sub_fc0d0126>", startup_body, "Expected tail branch to sub_fc0d0126 after CreateTask")

            # Ensure blx r4 occurs after the final ladder pulse frame-end delay (#4194304 = 0x400000)
            last_frame_gap_pos = startup_body.rfind("#4194304")
            blx_r4_pos = startup_body.rfind("blx\tr4")
            handoff_pos = startup_body.rfind("<sub_fc0d0126>")
            self.assertGreater(last_frame_gap_pos, 0)
            self.assertGreater(blx_r4_pos, last_frame_gap_pos, "CreateTask must be called after ladder Code 44 completes")
            self.assertGreater(handoff_pos, blx_r4_pos, "sub_fc0d0126 handoff must immediately follow CreateTask")

            # 3. Extract g3x_resident_heartbeat_task and verify LED register & ~1 Hz double-blink pattern
            m_hb = re.search(
                r"<g3x_resident_heartbeat_task>:(.*?)(?:\n\n|\Z)",
                disasm,
                re.DOTALL,
            )
            self.assertIsNotNone(m_hb, "g3x_resident_heartbeat_task not found in candidate_main.elf disassembly")
            hb_body = m_hb.group(1)

            self.assertEqual(G3X_RESIDENT_CREATETASK_ADDR, 0xBFE14A3D)
            self.assertIn("d20b0884", hb_body, "Heartbeat task must use PORT-25 LED MMIO 0xD20B0884")
            self.assertIn("004d0002", hb_body, "Heartbeat task must use PORT-25 LED ON value 0x004D0002")
            self.assertIn("004c0003", hb_body, "Heartbeat task must use PORT-25 LED OFF value 0x004C0003")
            self.assertIn("fc31bf84", hb_body, "Heartbeat task must use manifest-cited SleepTask veneer 0xFC31BF84")
            self.assertIn("bfe14a3d", hb_body, "CreateTask 0xBFE14A3D literal must be present")
            self.assertIn("#100", hb_body, "Heartbeat task must use 100 ms short pulse/gap delay")
            self.assertIn("#700", hb_body, "Heartbeat task must use 700 ms pause delay (100+100+100+700 = 1000 ms = 1 Hz)")

    def test_e_assumptions_table_and_repo_cleanliness(self) -> None:
        """(e) docs/PORT32_RESIDENT_CANDIDATE.md has required assumptions and FINSIG cross-check tables and no binaries are committed."""
        doc_path = DOCS_DIR / "PORT32_RESIDENT_CANDIDATE.md"
        self.assertTrue(doc_path.is_file(), f"Missing {doc_path}")
        doc_text = doc_path.read_text(encoding="utf-8")

        # Verify assumptions table header columns and FINSIG cross-check table header columns
        self.assertIn(
            "| assumption | label (VERIFIED/INFERRED/UNKNOWN) | citation | owner observation that confirms/refutes |",
            doc_text,
        )
        self.assertIn(
            "| candidate value | FINSIG value (reference/finsig_gm110c/stubs_entry.S or funcs_by_name.csv, path:line) | closest sibling DIGIC 6 port usage (chdk-port/platform/<port>/...:line) | match/mismatch |",
            doc_text,
        )

        # Verify required assumptions and FINSIG cross-check rows are covered
        required_topics = [
            "0xBFE14A3D",
            "0xbfe14a3d",
            "0xbfe14a3c",
            "0xFCEF3488",
            "FINSIG",
            "reference/finsig_gm110c/stubs_entry.S",
            "reference/finsig_gm110c/funcs_by_name.csv",
            "chdk-port/platform/g5x/sub/100c/boot.c",
            "chdk-port/platform/g7x/sub/100d/boot.c",
            "chdk-port/platform/sx710hs/sub/100a/boot.c",
            "match",
            "mismatch",
            "r0",
            "r1",
            "r2",
            "Stack alignment at task entry",
            "r3",
            "sp[0]",
            "0x2000",
            "0x19",
            "SleepTask",
            "0x00368680",
            "0xD20B0884",
            "0xFC0D0126",
            "VERIFIED",
            "INFERRED",
            "UNKNOWN",
        ]
        for topic in required_topics:
            self.assertIn(topic, doc_text, f"Missing required assumption topic {topic!r} in {doc_path}")

        # Verify delay unit and stack alignment at entry are labelled INFERRED in both code and docs
        hdr_text = (SUB_DIR / "led_breadcrumb.h").read_text(encoding="utf-8")
        self.assertIn("INFERRED delay unit: milliseconds", hdr_text)
        self.assertIn("Stack alignment at task entry is INFERRED", hdr_text)

        # Verify builder refuses to write into tracked repository directories
        for forbidden in [
            str(REPO_ROOT),
            str(CHDK_PORT / "out"),
            str(DOCS_DIR / "out"),
            str(TOOLS_DIR / "out"),
            str(EVIDENCE_DIR / "out"),
        ]:
            with self.assertRaises(ValueError):
                build_candidate(ladder=True, poweron_fix=True, out_dir=forbidden, resident=True)

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_f_spawn_preserves_r0_r3_and_sp_and_no_inline_sp_write_in_c_body(self) -> None:
        """(f) Spawn saves/restores r0-r3 and balances sp around CreateTask; no inline sp write in C task body."""
        hdr_text = (SUB_DIR / "led_breadcrumb.h").read_text(encoding="utf-8")

        # 1. Verify no inline-asm sp write (g3x_resident_align_sp) in led_breadcrumb.h or resident C body
        self.assertNotIn("g3x_resident_align_sp", hdr_text)
        self.assertNotIn("g3x_resident_align_sp", BOOT_PROTOTYPE_RESIDENT_C)
        self.assertNotIn("mov     sp, r0", hdr_text.split("#if defined(G3X_RESIDENT)")[1])

        # 2. Verify disassembly of spawn sequence and C task body
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, resident=True)
            proc = subprocess.run(
                [str(ARM_OBJDUMP), "-d", res["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            disasm = proc.stdout

            # Extract task_Startup_my post-Code-44 spawn sequence
            m_startup = re.search(r"<task_Startup_my>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_startup)
            startup_body = m_startup.group(1)

            # Find the end of CORE_LADDER_PULSE_44 (ldmia.w sp!, {r0, r1, r2, r3, ip, lr})
            end_code44_pos = startup_body.rfind("ldmia.w\tsp!, {r0, r1, r2, r3, ip, lr}")
            self.assertGreater(end_code44_pos, 0, "Expected end of CORE_LADDER_PULSE_44 frame pop")
            spawn_to_handoff = startup_body[end_code44_pos:]

            # Verify exact order: push {r0, r1, r2, r3} -> sub sp, #8 -> blx r4 -> add sp, #8 -> pop {r0, r1, r2, r3} -> ldmia.w sp!, {r4, lr} -> b.w sub_fc0d0126
            pos_push_r0_r3 = spawn_to_handoff.find("push\t{r0, r1, r2, r3}")
            pos_sub_sp = spawn_to_handoff.find("sub\tsp, #8")
            pos_blx_r4 = spawn_to_handoff.find("blx\tr4")
            pos_add_sp = spawn_to_handoff.find("add\tsp, #8")
            pos_pop_r0_r3 = spawn_to_handoff.find("pop\t{r0, r1, r2, r3}")
            pos_pop_r4_lr = spawn_to_handoff.find("ldmia.w\tsp!, {r4, lr}")
            pos_b_handoff = spawn_to_handoff.find("<sub_fc0d0126>")

            self.assertGreater(pos_push_r0_r3, 0, "Spawn must push {r0, r1, r2, r3}")
            self.assertGreater(pos_sub_sp, pos_push_r0_r3, "sub sp, #8 must follow push {r0, r1, r2, r3}")
            self.assertGreater(pos_blx_r4, pos_sub_sp, "blx r4 (CreateTask) must follow sub sp, #8")
            self.assertGreater(pos_add_sp, pos_blx_r4, "add sp, #8 must follow blx r4")
            self.assertGreater(pos_pop_r0_r3, pos_add_sp, "pop {r0, r1, r2, r3} must follow add sp, #8")
            self.assertGreater(pos_pop_r4_lr, pos_pop_r0_r3, "pop.w {r4, lr} must follow pop {r0, r1, r2, r3}")
            self.assertGreater(pos_b_handoff, pos_pop_r4_lr, "b.w sub_fc0d0126 must follow pop.w {r4, lr}")

            # Verify g3x_resident_heartbeat_task has 8-byte aligned compiler prologue (push {r7, lr}) and no sp writes
            m_hb = re.search(r"<g3x_resident_heartbeat_task>:(.*?)(?:\n\n|\Z)", disasm, re.DOTALL)
            self.assertIsNotNone(m_hb)
            hb_body = m_hb.group(1)
            self.assertIn("push\t{r7, lr}", hb_body, "Expected 8-byte aligned compiler prologue push {r7, lr}")
            self.assertNotIn("mov\tsp", hb_body, "No inline sp write allowed in g3x_resident_heartbeat_task")
            self.assertNotIn("sub\tsp", hb_body, "No manual sp adjustment in g3x_resident_heartbeat_task")

    @unittest.skipUnless(HAVE_TOOLCHAIN, "Pinned ARM toolchain required")
    def test_g_linked_end_within_heap_start_and_manifest_accurate(self) -> None:
        """(g) Linked _end read from linker output is <= resident heap start, and manifest records real linked _end."""
        with tempfile.TemporaryDirectory() as tmpdir:
            res = build_candidate(ladder=True, poweron_fix=True, out_dir=tmpdir, resident=True)

            # 1. Read actual linked _end directly from linker output (nm -n on candidate_main.elf)
            nm_proc = subprocess.run(
                [str(ARM_NM), "-n", res["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            linked_end = extract_symbol_addr_from_nm(nm_proc.stdout, "_end")
            self.assertEqual(linked_end, PINNED_PORT32_RESIDENT_END_ADDR)
            self.assertEqual(os.path.getsize(res["core_bin"]), PINNED_PORT32_RESIDENT_MAIN_SIZE)

            # 2. Read the heap start actually passed in sub_fc05b3c8_my disassembly and metadata
            objdump_proc = subprocess.run(
                [str(ARM_OBJDUMP), "-d", res["core_elf"]],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                check=True,
            )
            m_heap = re.search(r"<sub_fc05b3c8_my>:(.*?)<sub_fc05b558_my>:", objdump_proc.stdout, re.DOTALL)
            self.assertIsNotNone(m_heap)
            self.assertIn("00368680", m_heap.group(1), "sub_fc05b3c8_my must load 0x00368680 as heap start")
            passed_heap_start = int(res["heap_start_addr"], 16)
            self.assertEqual(passed_heap_start, G3X_RESIDENT_HEAP_START)

            # 3. Assert linked _end <= heap start (no DryOS heap overlap with CHDK image)
            self.assertLessEqual(
                linked_end,
                passed_heap_start,
                f"Linked _end (0x{linked_end:08X}) must be <= heap start (0x{passed_heap_start:08X})",
            )

            # 4. Assert manifest and build metadata _end equal the actual linked _end (not the heap constant)
            self.assertEqual(int(res["core_end_addr"], 16), linked_end)
            with open(res["manifest_path"], "r", encoding="utf-8") as f:
                manifest = json.load(f)
            inv = manifest["architectural_invariants"]
            self.assertEqual(int(inv["core_end_symbol"], 16), linked_end)
            self.assertNotEqual(int(inv["core_end_symbol"], 16), passed_heap_start)
            self.assertEqual(int(inv["dryos_heap_base"], 16), passed_heap_start)


if __name__ == "__main__":
    unittest.main()
