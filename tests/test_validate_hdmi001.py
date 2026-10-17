"""Offline regression tests for tools/validate_hdmi001_script.py.

Run from anywhere:  python3 -m unittest discover -s <repo>/tests -v
ROM-dependent tests are skipped when the proprietary dump is absent (e.g. CI).
"""

import importlib.util
import struct
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCRIPT = REPO / "firmware/tools/hdmi001_clean_overlay_gm110c.m"
ROM = REPO / "firmware/dumps/GM1.10C/PRIMARY.BIN"

_spec = importlib.util.spec_from_file_location("v", REPO / "tools/validate_hdmi001_script.py")
v = importlib.util.module_from_spec(_spec)
sys.modules["v"] = v
_spec.loader.exec_module(v)


def errs(text: str):
    return v.validate_script_text(text.encode("ascii", "replace"))["errors"]


class ScriptValidation(unittest.TestCase):
    def setUp(self):
        self.src = SCRIPT.read_text(encoding="ascii")

    def test_reviewed_script_passes(self):
        self.assertEqual(errs(self.src), [])

    def test_crlf_rejected(self):
        self.assertTrue(any("CR bytes" in e for e in errs(self.src.replace("\n", "\r\n"))))

    def test_non_ascii_rejected(self):
        raw = self.src.encode("ascii") + b"' \xc3\xa9\n"
        self.assertTrue(any("non-ASCII" in e for e in v.validate_script_text(raw)["errors"]))

    def test_each_guard_required(self):
        for g in v.REQUIRED_GUARDS:
            with self.subTest(guard=g):
                self.assertTrue(errs(self.src.replace(g, "if 0 = 1 then", 1)), g)

    def test_wrong_table_address_rejected(self):
        bad = self.src.replace("DIM expected_table_addr = 0x001231b8", "DIM expected_table_addr = 0x00123140")
        self.assertTrue(any("expected_table_addr" in e for e in errs(bad)))

    def test_gm110e_offsets_rejected(self):
        bad = self.src.replace("0xfc54e08d", "0xfc54e0b5")
        self.assertTrue(any("Forbidden address 0xFC54E0B5" in e for e in errs(bad)))

    def test_unreviewed_literal_rejected(self):
        bad = self.src.replace("DIM msg = 0", "DIM msg = 0\nDIM extra = 0x00015dc0")
        self.assertTrue(any("Unreviewed hex literal" in e for e in errs(bad)))

    def test_extra_poke_rejected(self):
        bad = self.src.replace("toggle_palette = 1", "Poke32(palette_control, 0)\n\t\ttoggle_palette = 1")
        self.assertTrue(any("Poke32" in e for e in errs(bad)))

    def test_third_poke8_rejected(self):
        bad = self.src.replace("toggle_palette = 2", "Poke8(palette_control, 3)\n\t\ttoggle_palette = 2")
        self.assertTrue(any("Poke8 called 3" in e for e in errs(bad)))

    def test_write_before_guard_rejected(self):
        bad = self.src.replace("\tif *slot <> expected_magic then",
                               "\tmemset(payload, 0, 1024)\n\tif *slot <> expected_magic then", 1)
        self.assertTrue(errs(bad))

    def test_write_outside_toggle_rejected(self):
        bad = self.src.replace("\tsetup()\n", "\tsetup()\n\tPoke8(palette_control, 3)\n", 1)
        self.assertTrue(any("outside toggle_palette" in e or "Poke8 called" in e for e in errs(bad)))

    def test_ungated_toggle_rejected(self):
        bad = self.src.replace("if compat = 0 then", "if compat = 99 then")
        self.assertTrue(any("not gated" in e for e in errs(bad)))

    def test_unbalanced_if_rejected(self):
        bad = self.src.replace("\tend if\n\ttbl = *palette_buffer_ptr", "\ttbl = *palette_buffer_ptr", 1)
        self.assertTrue(any("Unbalanced if" in e for e in errs(bad)))

    def test_constant_reassignment_rejected(self):
        bad = self.src.replace("\ttbl = *palette_buffer_ptr", "\tpalette_to_zero = 1\n\ttbl = *palette_buffer_ptr")
        self.assertTrue(any("reassigned" in e for e in errs(bad)))

    def test_comment_literals_ignored(self):
        self.assertEqual(errs(self.src + "' note 0xdeadbeef\n"), [])


@unittest.skipUnless(ROM.is_file(), "proprietary GM1.10C ROM not present")
class RomInvariants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rom = ROM.read_bytes()

    def test_rom_report_passes(self):
        self.assertEqual(v.validate_rom_invariants(ROM)["errors"], [])

    def test_checks_detect_corruption(self):
        bad = bytearray(self.rom)
        off = 0xFC33D508 - v.ROM_BASE
        bad[off:off + 4] = struct.pack("<I", 0x00123141)
        self.assertFalse(v.rom_checks(bytes(bad))["scm_table_base_lit_0xfc33d508"])

    def test_restore_source_matches_alloc_source(self):
        # GetActive passes SCM_GetRomDefaultPalette(0) to PaletteClass_Create:
        # 0xFC77C8AC + 0*0x60C + 4 == the script's rom_default_pal0.
        self.assertEqual(struct.unpack_from("<I", self.rom, 0xFC33D61C - v.ROM_BASE)[0] + 4, 0xFC77C8B0)

    def test_payload_write_inside_allocation(self):
        # alloc 0x408; script touches slot+4 .. slot+4+1024 (<= 0x404) only
        self.assertLessEqual(4 + 1024, 0x408)

    def test_clean_state_detector_cannot_match_stock(self):
        w = lambda i: struct.unpack_from("<I", self.rom, 0xFC77C8B0 + 4 * i - v.ROM_BASE)[0]
        self.assertTrue(any(w(i) != 0 for i in (1, 2, 3)))


if __name__ == "__main__":
    unittest.main()
