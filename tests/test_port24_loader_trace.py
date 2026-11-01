#!/usr/bin/env python3
"""PORT-24 T2: Unit tests for loader execution trace and restart path analysis.

Validates that:
1. docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json:
   - Validates using tools/port11c_evidence_validator.py with 0 errors.
   - Contains approved ranges, each <= 4 KiB, and total bytes <= 32 KiB.
   - Contains no overlapping evidence slices.
   - If PRIMARY.BIN is present, slice SHA-256 digests match actual ROM dump on disk.
2. docs/PORT24_LOADER_TRACE.md:
   - File exists and contains the required '## Restart path' section.
   - Explains what gates StartDiskboot on power-on with exact citations.
   - Explains the repeated/long-press stock-boot observation and states whether a later
     power-on can skip StartDiskboot and under which conditions.
   - Connects the held power button to the O1 first-boot result (CONT_ATTEMPTED / FRESHNESS_UNVERIFIED).
   - Every claim bullet, numbered list item, and table row carries an epistemic label
     ([VERIFIED], [STATIC_VERIFIED], [INFERRED], [UNKNOWN], or [OWNER-REPORTED]).
   - Every ROM address (0xFC...... / 0xFD......) cited in the doc appears in an approved manifest range.
   - Concludes with a list of observable physical cues for the owner (used by T4).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import unittest

REPO_ROOT = Path(__file__).resolve().parent.parent
DOC_PATH = REPO_ROOT / "docs" / "PORT24_LOADER_TRACE.md"
MANIFEST_PATH = REPO_ROOT / "docs" / "agentbridge" / "PORT24_EVIDENCE_MANIFEST.json"
ROM_PATH = Path(
    os.environ.get(
        "PORT24_ROM_PATH",
        os.environ.get("PORT21_ROM_PATH", str(REPO_ROOT / "firmware" / "dumps" / "GM1.10C" / "PRIMARY.BIN")),
    )
)
VALIDATOR_TOOL = REPO_ROOT / "tools" / "port11c_evidence_validator.py"
ROM_BASE = 0xFC000000

APPROVED_ENTRIES = {
    "PORT24-ROM-BOOT-EARLY": (
        0xFC020000,
        0xFC0201FF,
        512,
        "23082470c3f8d0628c5b6661c2ddb2b2ca010c88e0afc8580754fa887b3a5b2f",
    ),
    "PORT24-ROM-STARTUP-TASKS": (
        0xFC05B8E0,
        0xFC05BBDF,
        768,
        "749dd4f383eec258850e14f1488b853c7902156f106a4924d54788f47fa35e0e",
    ),
    "PORT24-ROM-STARTDISKBOOT": (
        0xFC05BBEA,
        0xFC05BDE9,
        512,
        "a2ea19dfed6f386b32074c65ec682a557a24cf3ddcdeb73f29108ae16854acfc",
    ),
    "PORT24-ROM-CARD-SWITCHES": (
        0xFC05C4D0,
        0xFC05C51F,
        80,
        "886c3e10248cc33ac671b575331311bbaf59ae549ab01a9414ddb1b470c314c5",
    ),
    "PORT24-ROM-NORMAL-MODE": (
        0xFC079400,
        0xFC0794BF,
        192,
        "cc71c4d4d3014205a860babbed28baa316d475bf1932d2368b5b4cad983a8214",
    ),
    "PORT24-ROM-NORMAL-FLAG": (
        0xFDF20380,
        0xFDF2038F,
        16,
        "7998b107f5214f071a101c994a4c8081a9c4abcd72e3970049a923c4bc137f64",
    ),
    "PORT24-ROM-STARTCAUSE-SAVE": (
        0xFC08ECB0,
        0xFC08ECFF,
        80,
        "039ca184b58d48f853b02fd60a4ad72f45f389790e6da71c6488d99162f8277d",
    ),
    "PORT24-ROM-STARTCAUSE-PTR": (
        0xFC08EEE0,
        0xFC08EEFF,
        32,
        "0ceabc1be63a68d5c37a240c220c5e3e4448271ffa11c6d28c4a3d20e72506c6",
    ),
    "PORT24-ROM-TURNOFF-E1": (
        0xFC0D0120,
        0xFC0D023F,
        288,
        "e29e71a6f1e1c1259c5025683344a592dd927716ffdf6fcd74928b7cfff9f694",
    ),
    "PORT24-ROM-GPIO-PRIMITIVES": (
        0xFC0D73C0,
        0xFC0D74BF,
        256,
        "0559f26c1c0a384b2cf3aec384430fb318cf68aefe88cafeb958e1b783476c3b",
    ),
    "PORT24-ROM-PREPARE-EXEC": (
        0xFC0D9C00,
        0xFC0D9DFF,
        512,
        "8c891f7dc8fc758510f36a69d95ff323cee00a7ac0e853128d1be27d8598d644",
    ),
    "PORT24-ROM-POWERON-CHECK": (
        0xFC1284A0,
        0xFC1285DF,
        320,
        "634fd848e765cad5b01737956e6aea9ddd12dbb4413213ec2a9c3d2a421813d4",
    ),
    "PORT24-ROM-WATCHDOG-MODULE": (
        0xFC135C00,
        0xFC135E3F,
        576,
        "29a0c9a8b406aa86a8a971d6d0032273fbaa22510c224dfb9742284e643de9cb",
    ),
    "PORT24-ROM-VBR-CHECK": (
        0xFC37AE60,
        0xFC37AEFF,
        160,
        "fc69a8c1639c873ca00c80edca02bdccdc52b1396fbb90eedc49821463c3ce17",
    ),
    "PORT24-ROM-WATCHDOG-START": (
        0xFC418F20,
        0xFC418F7F,
        96,
        "46e8e2149df855d0f1414699a1fdea355b9370c83e552a749314a32283da7da5",
    ),
}

LABEL_PATTERN = re.compile(
    r"\[(?:VERIFIED|STATIC_VERIFIED|INFERRED|UNKNOWN|OWNER-REPORTED)[^\]]*\]"
)


class TestPort24EvidenceManifest(unittest.TestCase):
    """Validates docs/agentbridge/PORT24_EVIDENCE_MANIFEST.json constraints."""

    @classmethod
    def setUpClass(cls):
        cls.assertTrue(MANIFEST_PATH.is_file(), f"Manifest missing: {MANIFEST_PATH}")
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            cls.manifest = json.load(f)

    def test_validator_script_passes(self):
        """Manifest validates cleanly using port11c_evidence_validator.py."""
        self.assertTrue(VALIDATOR_TOOL.is_file(), f"Validator missing: {VALIDATOR_TOOL}")
        cmd = ["python3", str(VALIDATOR_TOOL), "--manifest", str(MANIFEST_PATH)]
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        self.assertEqual(
            res.returncode,
            0,
            f"Validator failed with code {res.returncode}:\nStdout:\n{res.stdout}\nStderr:\n{res.stderr}",
        )
        self.assertIn("Result: VALID", res.stdout)

    def test_max_window_and_total_byte_quota(self):
        """Each window <= 4 KiB (4096 B) and total bytes <= 32 KiB (32768 B)."""
        entries = self.manifest.get("evidence_entries", [])
        total_bytes = 0
        for entry in entries:
            eid = entry["evidence_id"]
            start = int(entry["start_address"], 16)
            end = int(entry["end_address"], 16)
            count = entry["expected_byte_count"]
            self.assertEqual(end - start + 1, count, f"Span mismatch for {eid}")
            self.assertLessEqual(count, 4096, f"Entry {eid} exceeds 4 KiB window: {count} B")
            total_bytes += count

        self.assertLessEqual(total_bytes, 32768, f"Total manifest bytes exceed 32 KiB: {total_bytes} B")

    def test_no_overlapping_ranges(self):
        """Approved ranges in manifest must not overlap."""
        entries = self.manifest.get("evidence_entries", [])
        sorted_entries = sorted(entries, key=lambda x: int(x["start_address"], 16))
        for i in range(len(sorted_entries) - 1):
            e1 = sorted_entries[i]
            e2 = sorted_entries[i + 1]
            end1 = int(e1["end_address"], 16)
            start2 = int(e2["start_address"], 16)
            self.assertLess(
                end1,
                start2,
                f"Overlap detected: {e1['evidence_id']} (end 0x{end1:08X}) overlaps "
                f"{e2['evidence_id']} (start 0x{start2:08X})",
            )

    def test_rom_dump_sha256_if_available(self):
        """Verify slice SHA-256 against actual PRIMARY.BIN if available."""
        if not ROM_PATH.is_file():
            self.skipTest(f"ROM dump not present at {ROM_PATH}")

        with open(ROM_PATH, "rb") as f:
            for eid, (start, end, count, expected_sha) in APPROVED_ENTRIES.items():
                offset = start - ROM_BASE
                f.seek(offset)
                slice_bytes = f.read(count)
                self.assertEqual(len(slice_bytes), count, f"ROM slice {eid} incomplete")
                actual_sha = hashlib.sha256(slice_bytes).hexdigest()
                self.assertEqual(actual_sha, expected_sha, f"SHA-256 mismatch for {eid}")


class TestPort24LoaderTraceDoc(unittest.TestCase):
    """Validates the contents, structure, and citations of docs/PORT24_LOADER_TRACE.md."""

    @classmethod
    def setUpClass(cls):
        cls.assertTrue(DOC_PATH.is_file(), f"Document missing: {DOC_PATH}")
        cls.content = DOC_PATH.read_text(encoding="utf-8")
        cls.lines = cls.content.splitlines()
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            cls.manifest = json.load(f)

    def test_restart_path_section_exists(self):
        """Check that ## Restart path section exists."""
        self.assertIn("## Restart path", self.content, "Section '## Restart path' missing")

    def test_gates_and_citations_covered(self):
        """Verifies explanation of what gates StartDiskboot on power-on with citations."""
        self.assertIn("sub_fc05b962", self.content)
        self.assertIn("sub_fc1284ac", self.content)
        self.assertIn("sub_fc05ba56", self.content)
        self.assertIn("task_Startup", self.content)
        self.assertIn("StartDiskboot", self.content)
        self.assertIn("0xFC05B8FC", self.content)
        self.assertIn("0xFC05B90E", self.content)
        self.assertIn("0xFC05BBEA", self.content)
        self.assertIn("0xFC05BC04", self.content)
        self.assertIn("BOOTDISK", self.content)
        self.assertIn("DISKBOOT.BIN", self.content)

    def test_explains_repeated_and_long_press_observation(self):
        """Section explains owner repeated/long-press observation and skips/survives conditions."""
        self.assertIn("long press", self.content.lower())
        self.assertIn("short press", self.content.lower())
        self.assertIn("O1", self.content)
        self.assertIn("CONT_ATTEMPTED", self.content)
        self.assertIn("FRESHNESS_UNVERIFIED", self.content)
        self.assertIn("0x0035F7A0", self.content)

    def test_observable_cues_list_present(self):
        """Section ends with a short list of observable cues that the owner can see by hand."""
        self.assertIn("Observable Cues for Hand Inspection", self.content)
        lower_content = self.content.lower()
        self.assertIn("green status led", lower_content)
        self.assertIn("hold duration", lower_content)
        self.assertIn("playback button", lower_content)
        self.assertIn("lock switch", lower_content)
        self.assertIn("witness inspector", lower_content)

    def test_all_claim_bullets_and_rows_carry_epistemic_labels(self):
        """Every claim bullet, numbered item, and table row carries an epistemic label."""
        unlabeled_bullets = []
        unlabeled_rows = []

        for i, line in enumerate(self.lines, start=1):
            stripped = line.strip()
            # Check bullets (- / *) or numbered list items (1. / 2.)
            if stripped.startswith(("- ", "* ")) or re.match(r"^\d+\.\s", stripped):
                # Exclude pure sub-bullet headers if any
                if not LABEL_PATTERN.search(stripped):
                    unlabeled_bullets.append(f"Line {i}: {stripped}")
            # Check table content rows (excluding separators and headers)
            elif stripped.startswith("|") and stripped.endswith("|"):
                if re.match(r"^\|[\s\-:|]+\|$", stripped):
                    continue
                if "Evidence ID" in stripped or "Start Address" in stripped:
                    continue
                if not LABEL_PATTERN.search(stripped):
                    unlabeled_rows.append(f"Line {i}: {stripped}")

        self.assertEqual(
            unlabeled_bullets,
            [],
            f"Found unlabeled bullets in docs/PORT24_LOADER_TRACE.md:\n"
            + "\n".join(unlabeled_bullets),
        )
        self.assertEqual(
            unlabeled_rows,
            [],
            f"Found unlabeled table rows in docs/PORT24_LOADER_TRACE.md:\n"
            + "\n".join(unlabeled_rows),
        )

    def test_every_cited_rom_address_appears_in_manifest_range(self):
        """Every 0xFC...... and 0xFD...... address in the markdown document falls within an approved manifest range."""
        scopes = self.manifest.get("authorization_scopes", [])
        approved_ranges = [
            (int(r["start_address"], 16), int(r["end_address"], 16), r["label"])
            for s in scopes
            for r in s.get("approved_ranges", [])
        ]

        # Assert on all ROM addresses (0xFC...... and 0xFD......) in document
        all_rom_addrs = set(re.findall(r"\b0xF[CD][0-9A-Fa-f]{6}\b", self.content))
        self.assertGreater(len(all_rom_addrs), 15, "Too few ROM addresses found in doc")

        unapproved_addrs = []
        for addr_str in sorted(all_rom_addrs):
            val = int(addr_str, 16)
            is_covered = any(start <= val <= end for start, end, _ in approved_ranges)
            if not is_covered:
                unapproved_addrs.append(addr_str)

        self.assertEqual(
            unapproved_addrs,
            [],
            f"Found ROM addresses outside approved manifest ranges in docs/PORT24_LOADER_TRACE.md:\n"
            + "\n".join(unapproved_addrs),
        )


if __name__ == "__main__":
    unittest.main()
