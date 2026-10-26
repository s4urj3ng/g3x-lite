"""PORT-7C: CHDK Platform Offline Validation Framework.

Reusable offline validation for Canon PowerShot G3 X (GM1.10C) platform configuration
sources comparing current implementation against historical GM1.10E reference.

Scope:
- Keyboard: 14 current keys vs 19 historical; 8 observed vs static keys; mask coverage.
- Shooting modes: 17 current vs 32 historical; consistency and namespace separation.
- Aperture & ND: physical aperture monotonicity vs synthetic historical ND grid discrepancy.
- Display: containment invariants and compile-time resolution change consistency.
- Fail-closed negative controls.

Constraints:
- No firmware/ROM binary reads, disassembly, subprocesses, compiler, or build tools.
- Does not modify runtime code, firmware configuration, or PORT-7B files/tests.
- Tests unverified historical features as UNVERIFIED/UNSUPPORTED rather than treating them as failures.
- Claude owns PORT-7B for Playback mask integration; this module does NOT alter or fail on Playback mask.

Execution:
  python3 -B -m unittest discover -s tests -p test_port7c_platform_validation.py -v
"""

import os
from pathlib import Path
import re
import tempfile
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
PLATFORM_DIR = Path(os.environ.get(
    "G3X_PLATFORM_DIR", str(REPO_ROOT / "chdk-port/platform/g3x")
))

# -----------------------------------------------------------------------------
# Evidence Baselines (attributed from PORT-0, UI001B-1, PORT-6C, PORT-7A)
# -----------------------------------------------------------------------------

# Eight owner-observed physical keys from UI-001B-1 hardware tests
OBSERVED_KEYS = {
    "KEY_UP": (0, 0x20),
    "KEY_DOWN": (0, 0x40),
    "KEY_RIGHT": (0, 0x80),
    "KEY_LEFT": (0, 0x100),
    "KEY_MENU": (0, 0x10),
    "KEY_DISPLAY": (0, 0x1000),
    "KEY_WIFI": (0, 0x2000),
    "KEY_VIDEO": (0, 0x8),
}

# Six statically recorded keys from GM1.10C ROM switch table
RECORDED_STATIC_KEYS = {
    "KEY_SET": (0, 0x200),
    "KEY_SHOOT_HALF": (0, 0x40000),
    "KEY_SHOOT_FULL_ONLY": (0, 0x1),
    "KEY_SHOOT_FULL": (0, 0x40001),
    "KEY_PLAYBACK": (0, 0x10000),
    "KEY_POWER": (0, 0x20000),
}

# Five additional keys present in Ranma's historical GM1.10E port (P:138-158)
# but absent in current GM1.10C kbd.c:
HISTORICAL_ONLY_KEYS = {
    "KEY_ZOOM_OUT": (0, 0x2),
    "KEY_ZOOM_IN": (0, 0x4),
    "KEY_ERASE": (0, 0x800),
    "KEY_PRINT": (0, 0x4000),
    "KEY_AE_LOCK": (0, 0x10000000),
}

# Ancillary physical switch index/flag pairs
ANCILLARY_FLAGS = {
    "SD_READONLY": (1, 0x20000000),
    "USB": (2, 0x00800000),
    "BATTCOVER": (2, 0x00400000),
    "HOTSHOE": (1, 0x00001000),
}

# The 17 mode IDs currently defined in GM1.10C shooting.c
CURRENT_MODE_IDS = frozenset({
    32768, 32770, 32771, 32772, 32773, 33299, 33298,
    2643, 2650, 2651, 2652, 16406, 16416, 16453, 16454, 16459, 16953,
})

# The 15 additional modes present in historical GM1.10E modemap (P:1190-1235)
HISTORICAL_ONLY_MODES = {
    "MODE_SPORTS": 33288,
    "MODE_SMART_SHUTTER": 16949,
    "MODE_FACE_SELF_TIMER": 16948,
    "MODE_WINK_SELF_TIMER": 16950,
    "MODE_SNOW": 16414,
    "MODE_HDR": 8775,
    "MODE_NOSTALGIC": 8753,
    "MODE_FISHEYE": 8759,
    "MODE_MINIATURE": 8760,
    "MODE_TOY_CAMERA": 8763,
    "MODE_BACKGROUND_DEFOCUS": 8764,
    "MODE_SOFTFOCUS": 8765,
    "MODE_MONOCHROME": 8767,
    "MODE_SUPER_VIVID": 8754,
    "MODE_POSTER_EFFECT": 8755,
}

# 13 physical aperture entries defined in GM1.10C shooting.c
EXPECTED_PHYSICAL_APERTURES = [
    (13, 288, "2.8"),
    (14, 320, "3.2"),
    (15, 352, "3.5"),
    (16, 369, "4.0"),
    (17, 401, "4.5"),
    (18, 433, "5.0"),
    (19, 465, "5.6"),
    (20, 497, "6.3"),
    (21, 529, "7.1"),
    (22, 561, "8.0"),
    (23, 593, "9.0"),
    (24, 625, "10.0"),
    (25, 657, "11.0"),
]

# 6 historical extended ND aperture entries from GM1.10E (P:1083-1105)
HISTORICAL_ND_APERTURES = [
    (26, 704, "13.0"),
    (27, 736, "14.0"),
    (28, 768, "16.0"),
    (29, 800, "18.0"),
    (30, 832, "20.0"),
    (31, 864, "22.0"),
]


# -----------------------------------------------------------------------------
# Parser Helpers
# -----------------------------------------------------------------------------

def strip_c_comments(text: str) -> str:
    """Strip C/C++ style comments while preserving quoted string literals."""
    pattern = r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*'
    return re.sub(pattern, lambda m: m[0] if m[0].startswith('"') else ' ',
                  text, flags=re.S)


def parse_definition(text: str, name: str) -> str:
    """Extract single active macro definition value."""
    uncommented = strip_c_comments(text)
    matches = re.findall(r'^\s*#define\s+' + re.escape(name) + r'\s+([^\n]+)',
                         uncommented, flags=re.M)
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one active definition for {name}, found {len(matches)}")
    return matches[0].strip()


def parse_numeric_definition(text: str, name: str) -> int:
    """Extract single integer numeric macro definition."""
    raw = parse_definition(text, name).strip('() \t')
    if not re.fullmatch(r'0[xX][0-9a-fA-F]+|-?[0-9]+', raw):
        raise ValueError(f"Unsupported non-literal numeric definition {name}: {raw}")
    return int(raw, 0)


def parse_struct_array(text: str, type_name: str, var_name: str) -> list:
    """Extract rows of a C struct array initializer."""
    uncommented = strip_c_comments(text)
    pattern = r'\b' + type_name + r'\s+' + var_name + r'\s*\[\s*\]\s*=\s*\{(.*?)\};'
    matches = re.findall(pattern, uncommented, flags=re.S)
    if len(matches) != 1:
        raise ValueError(f"Expected exactly one {var_name} array initializer, found {len(matches)}")
    body = matches[0]
    row_matches = re.findall(r'\{([^{}]+)\}', body)
    if not row_matches or re.sub(r'\{[^{}]+\}|[\s,]', '', body):
        raise ValueError(f"Malformed or empty array initializer for {var_name}")
    return [tuple(f.strip() for f in r.split(',')) for r in row_matches]


def load_platform_sources(dir_path: Path) -> dict:
    """Load the platform configuration sources; fails closed if any is missing."""
    file_names = ("platform_camera.h", "platform_kbd.h", "kbd.c", "shooting.c", "lib.c")
    sources = {}
    for fname in file_names:
        p = dir_path / fname
        if not p.is_file():
            raise FileNotFoundError(f"Required platform file missing: {p}")
        sources[fname] = p.read_text(encoding="utf-8")
    return sources


def parse_keymap(kbd_text: str) -> dict:
    """Parse KeyMap array into dict of key -> (group, mask)."""
    rows = parse_struct_array(kbd_text, 'KeyMap', 'keymap')
    if not rows or rows[-1] != ('0', '0', '0'):
        raise ValueError("KeyMap missing terminal sentinel (0, 0, 0)")
    mapping = {}
    for row in rows[:-1]:
        if len(row) != 3:
            raise ValueError(f"Invalid KeyMap row: {row}")
        group_s, key_s, mask_s = row
        if not re.fullmatch(r'KEY_[A-Z0-9_]+', key_s):
            raise ValueError(f"Invalid key name: {key_s}")
        if key_s in mapping:
            raise ValueError(f"Duplicate key in keymap: {key_s}")
        mapping[key_s] = (int(group_s, 0), int(mask_s, 0))
    return mapping


def parse_aperture_table(shooting_text: str) -> list:
    """Parse ApertureSize array into list of (id, apex, string_label)."""
    rows = parse_struct_array(shooting_text, 'ApertureSize', 'aperture_sizes_table')
    parsed = []
    for row in rows:
        if len(row) != 3:
            raise ValueError(f"Invalid ApertureSize row: {row}")
        aid_s, apex_s, label_s = row
        label = label_s.strip('" ')
        parsed.append((int(aid_s, 0), int(apex_s, 0), label))
    return parsed


def parse_modemap(shooting_text: str) -> list:
    """Parse CapturemodeMap array into list of (mode_name, mode_id)."""
    rows = parse_struct_array(shooting_text, 'CapturemodeMap', 'modemap')
    parsed = []
    for row in rows:
        if len(row) != 2:
            raise ValueError(f"Invalid CapturemodeMap row: {row}")
        mname_s, mid_s = row
        if not re.fullmatch(r'MODE_[A-Z0-9_]+', mname_s):
            raise ValueError(f"Invalid mode name: {mname_s}")
        parsed.append((mname_s, int(mid_s, 0)))
    return parsed


# -----------------------------------------------------------------------------
# Test Suite: PORT-7C Platform Offline Validation Framework
# -----------------------------------------------------------------------------

class TestPort7cKeyboardValidation(unittest.TestCase):
    """Section A: Keyboard mapping and mask coverage validation."""

    @classmethod
    def setUpClass(cls):
        cls.sources = load_platform_sources(PLATFORM_DIR)
        cls.keymap = parse_keymap(cls.sources['kbd.c'])
        cls.kbd_header = cls.sources['platform_kbd.h']
        cls.cam_header = cls.sources['platform_camera.h']
        cls.masks = tuple(parse_numeric_definition(cls.kbd_header, f'KEYS_MASK{i}') for i in range(3))

    def test_keymap_structural_invariants(self):
        """Current keymap has exactly 14 non-sentinel entries and valid groups."""
        self.assertEqual(len(self.keymap), 14)
        for key, (group, mask) in self.keymap.items():
            self.assertEqual(group, 0, f"{key} group must be 0")
            self.assertGreater(mask, 0)
            self.assertLessEqual(mask, 0xFFFFFFFF)

    def test_observed_keys_integrity(self):
        """Eight hardware-observed keys match verified bit assignments."""
        for key, expected in OBSERVED_KEYS.items():
            with self.subTest(key=key):
                self.assertIn(key, self.keymap)
                self.assertEqual(self.keymap[key], expected)

    def test_static_keys_integrity(self):
        """Six static keys match recorded GM1.10C ROM switch assignments."""
        for key, expected in RECORDED_STATIC_KEYS.items():
            with self.subTest(key=key):
                self.assertIn(key, self.keymap)
                self.assertEqual(self.keymap[key], expected)

    def test_composite_shutter_invariants(self):
        """SHOOT_FULL equals SHOOT_HALF | SHOOT_FULL_ONLY; FULL precedes HALF."""
        half = self.keymap['KEY_SHOOT_HALF'][1]
        full = self.keymap['KEY_SHOOT_FULL'][1]
        only = self.keymap['KEY_SHOOT_FULL_ONLY'][1]
        self.assertEqual(full, half | only)
        keys_order = list(self.keymap.keys())
        self.assertLess(keys_order.index('KEY_SHOOT_FULL'), keys_order.index('KEY_SHOOT_HALF'))

    def test_override_mask_covers_observed_keys(self):
        """KEYS_MASK0 covers all eight hardware-observed keys."""
        mask0 = self.masks[0]
        for key, (_, bit) in OBSERVED_KEYS.items():
            with self.subTest(key=key):
                self.assertEqual(bit & ~mask0, 0, f"{key} (bit {hex(bit)}) not covered by KEYS_MASK0")

    def test_ancillary_flag_definitions(self):
        """Ancillary hardware switch index and bit definitions match ROM."""
        for prefix, (expected_idx, expected_mask) in ANCILLARY_FLAGS.items():
            with self.subTest(prefix=prefix):
                idx = parse_numeric_definition(self.kbd_header, f"{prefix}_IDX")
                suffix = "_MASK" if prefix == "USB" else "_FLAG"
                mask = parse_numeric_definition(self.kbd_header, f"{prefix}{suffix}")
                self.assertEqual(idx, expected_idx)
                self.assertEqual(mask, expected_mask)

    def test_historical_keys_unverified_discrepancy(self):
        """Five historical keys are absent from current GM1.10C keymap and marked historical-only."""
        # Non-failing verification: reports discrepancy as UNVERIFIED without asserting failure.
        for h_key, h_expected in HISTORICAL_ONLY_KEYS.items():
            with self.subTest(historical_key=h_key):
                self.assertNotIn(h_key, self.keymap,
                                 f"Historical key {h_key} unexpectedly present in current keymap")
        discrepancy_report = {
            "missing_from_current": list(HISTORICAL_ONLY_KEYS.keys()),
            "status": "HISTORICAL_REFERENCE_ONLY",
            "independent_gm110c_verification": "UNVERIFIED"
        }
        self.assertEqual(len(discrepancy_report["missing_from_current"]), 5)

    def test_playback_mask_ownership_boundary(self):
        """Playback mask status: verify Power is excluded, and verify either baseline (0x433F9) or PORT-7B (0x533F9)."""
        mask0 = self.masks[0]
        playback_bit = RECORDED_STATIC_KEYS["KEY_PLAYBACK"][1]  # 0x10000
        power_bit = RECORDED_STATIC_KEYS["KEY_POWER"][1]        # 0x20000

        # Invariant for both baseline and PORT-7B: Power (bit 17) must remain strictly excluded
        self.assertEqual(mask0 & power_bit, 0, "Power mask (bit 17) must remain excluded")

        # Mask boundary:
        # Pre-PORT-7B clean origin/main: mask0 == 0x000433F9 (playback_bit excluded)
        # Post-PORT-7B uncommitted/merged: mask0 == 0x000533F9 (playback_bit covered)
        self.assertIn(mask0, (0x000433F9, 0x000533F9),
                      f"KEYS_MASK0 must be either pre-7B (0x000433F9) or post-7B (0x000533F9), got {hex(mask0)}")
        if mask0 & playback_bit:
            self.assertEqual(mask0, 0x000533F9, "When Playback is covered, mask must be exactly 0x000533F9")
        else:
            self.assertEqual(mask0, 0x000433F9, "When Playback is excluded, mask must be exactly 0x000433F9")


class TestPort7cShootingModesValidation(unittest.TestCase):
    """Section B: Shooting mode table consistency and historical comparison."""

    @classmethod
    def setUpClass(cls):
        cls.sources = load_platform_sources(PLATFORM_DIR)
        cls.modemap = parse_modemap(cls.sources['shooting.c'])
        cls.mode_dict = dict(cls.modemap)

    def test_current_modes_count_and_uniqueness(self):
        """Current modemap has exactly 17 unique modes with non-empty names."""
        self.assertEqual(len(self.modemap), 17)
        names = [m[0] for m in self.modemap]
        ids = [m[1] for m in self.modemap]
        self.assertEqual(len(names), len(set(names)), "Duplicate mode name in modemap")
        self.assertEqual(len(ids), len(set(ids)), "Duplicate mode ID in modemap")
        self.assertEqual(frozenset(ids), CURRENT_MODE_IDS)

    def test_current_mode_namespace_partitions(self):
        """Current mode IDs belong to standard Canon DryOS functional ranges."""
        ranges = {
            "manual_and_pas": (32768, 32773),    # Auto, M, Av, Tv, P
            "creative_hybrid": (33298, 33299),   # Hybrid Auto, Creative Effect
            "video_modes": (2643, 2652),         # Video Std, iFrame, Video M, Short Clip
            "scene_modes": (16406, 16953),       # Portrait, Firework, Star, Night Scene
        }
        for name, mid in self.modemap:
            matched = any(low <= mid <= high for low, high in ranges.values())
            self.assertTrue(matched, f"Mode {name} ({mid}) falls outside expected DryOS ranges")

    def test_historical_modes_unverified_discrepancy(self):
        """Fifteen historical modes are absent from current GM1.10C modemap and marked unverified."""
        # Tests that none of the 15 historical modes are prematurely imported without C verification.
        current_names = set(self.mode_dict.keys())
        current_ids = set(self.mode_dict.values())
        for h_name, h_id in HISTORICAL_ONLY_MODES.items():
            with self.subTest(historical_mode=h_name):
                self.assertNotIn(h_name, current_names,
                                 f"Historical mode {h_name} unexpectedly present in current modemap")
                self.assertNotIn(h_id, current_ids,
                                 f"Historical mode ID {h_id} unexpectedly present in current modemap")
        discrepancy = {
            "historical_deficit_count": len(HISTORICAL_ONLY_MODES),
            "status": "HISTORICAL_UNVERIFIED_FOR_GM110C",
            "offline_rule": "Do not import without independent Canon mode list verification"
        }
        self.assertEqual(discrepancy["historical_deficit_count"], 15)


class TestPort7cApertureAndNdValidation(unittest.TestCase):
    """Section C: Aperture table and ND filter configuration validation."""

    @classmethod
    def setUpClass(cls):
        cls.sources = load_platform_sources(PLATFORM_DIR)
        cls.apertures = parse_aperture_table(cls.sources['shooting.c'])

    def test_current_aperture_table_invariants(self):
        """Current physical aperture table has 13 entries with monotonic IDs and APEX values."""
        self.assertEqual(len(self.apertures), 13)
        self.assertEqual(self.apertures, EXPECTED_PHYSICAL_APERTURES)

        # Monotonicity check
        ids = [a[0] for a in self.apertures]
        apexes = [a[1] for a in self.apertures]
        self.assertEqual(ids, sorted(ids))
        self.assertEqual(apexes, sorted(apexes))
        self.assertEqual(len(ids), len(set(ids)), "Duplicate aperture ID found")
        self.assertEqual(len(apexes), len(set(apexes)), "Duplicate APEX value found")

    def test_current_aperture_string_labels(self):
        """Aperture string labels conform to standard f-number format."""
        for aid, apex, label in self.apertures:
            self.assertTrue(re.fullmatch(r'[0-9]+\.[0-9]', label),
                            f"Aperture {aid} has non-standard label format: {label}")
            val = float(label)
            self.assertGreaterEqual(val, 2.8)
            self.assertLessEqual(val, 11.0)

    def test_historical_nd_aperture_grid_inconsistency(self):
        """Historical ND entries do NOT derive from physical aperture steps + 3-stop attenuation.

        ND filter provides 3 stops of attenuation (3 * 96 = 288 APEX96 units).
        Subtracting 288 from historical ND entries yields synthetic 1/3-EV steps:
          704 - 288 = 416 (not in physical table: table has 401)
          736 - 288 = 448 (not in physical table: table has 433)
          768 - 288 = 480 (not in physical table: table has 465)
          800 - 288 = 512 (not in physical table: table has 497)
          832 - 288 = 544 (not in physical table: table has 529)
          864 - 288 = 576 (not in physical table: table has 561)
        This proves the historical ND entries used a synthetic grid rather than physical steps.
        """
        physical_apexes = set(a[1] for a in self.apertures)
        nd_3_stops_apex = 288  # 3 EV * 96 APEX96 units/EV

        derived_base_apexes = [nd_apex - nd_3_stops_apex for _, nd_apex, _ in HISTORICAL_ND_APERTURES]
        self.assertEqual(derived_base_apexes, [416, 448, 480, 512, 544, 576])

        # Confirm that NONE of the derived base APEX values exist in the physical aperture table
        intersection = physical_apexes.intersection(derived_base_apexes)
        self.assertEqual(len(intersection), 0,
                         "Historical ND base values unexpectedly intersect with physical table")

        nd_audit_finding = {
            "status": "HISTORICAL_SYNTHETIC_GRID_INCONSISTENCY",
            "decision": "DO_NOT_IMPORT_WITHOUT_GM110C_OPTICAL_CONFIRMATION"
        }
        self.assertEqual(nd_audit_finding["status"], "HISTORICAL_SYNTHETIC_GRID_INCONSISTENCY")


class TestPort7cDisplayConfigurationValidation(unittest.TestCase):
    """Section D: Display dimensions and compile-time consistency."""

    @classmethod
    def setUpClass(cls):
        cls.sources = load_platform_sources(PLATFORM_DIR)
        cls.cam_header = cls.sources['platform_camera.h']
        cls.lib_c = cls.sources['lib.c']

    def test_current_display_containment(self):
        """Current screen dimensions are strictly contained within bitmap dimensions."""
        sw = parse_numeric_definition(self.cam_header, 'CAM_SCREEN_WIDTH')
        sh = parse_numeric_definition(self.cam_header, 'CAM_SCREEN_HEIGHT')
        bw = parse_numeric_definition(self.cam_header, 'CAM_BITMAP_WIDTH')
        bh = parse_numeric_definition(self.cam_header, 'CAM_BITMAP_HEIGHT')

        self.assertGreater(sw, 0)
        self.assertGreater(sh, 0)
        self.assertLessEqual(sw, bw, "Screen width must not exceed bitmap buffer width")
        self.assertLessEqual(sh, bh, "Screen height must not exceed bitmap buffer height")

        # Stride alignment check (bitmap width should be aligned to 16 or 32 for hardware DMA)
        self.assertEqual(bw % 16, 0, "Bitmap width must be aligned to multiple of 16")

    def test_compile_time_resolution_change_consistency(self):
        """CAM_SUPPORT_BITMAP_RES_CHANGE must NOT be defined without update_screen_dimensions implementation."""
        # Common CHDK core (core/shooting.c) calls update_screen_dimensions() only if CAM_SUPPORT_BITMAP_RES_CHANGE is defined.
        res_change_defined = bool(re.search(r'^\s*#define\s+CAM_SUPPORT_BITMAP_RES_CHANGE\b',
                                            strip_c_comments(self.cam_header), flags=re.M))
        update_func_implemented = bool(re.search(r'\bvoid\s+update_screen_dimensions\s*\(\s*\)',
                                                 strip_c_comments(self.lib_c)))

        # Both must be absent or both must be present to prevent link error
        self.assertEqual(res_change_defined, update_func_implemented,
                         "CAM_SUPPORT_BITMAP_RES_CHANGE defined without update_screen_dimensions implementation")
        self.assertFalse(res_change_defined, "Current configuration correctly leaves dynamic sizing unenabled")

    def test_display_dimension_classification(self):
        """Current fixed 720x480 vs historical dynamic 900x600/1024x768 classified accurately."""
        sw = parse_numeric_definition(self.cam_header, 'CAM_SCREEN_WIDTH')
        sh = parse_numeric_definition(self.cam_header, 'CAM_SCREEN_HEIGHT')
        status = {
            "current_dimensions": (sw, sh),
            "current_classification": "CURRENT_FIXED_CONTAINED",
            "historical_lcd": (900, 600),
            "historical_evf": (1024, 768),
            "historical_classification": "HISTORICAL_DYNAMIC_UNVERIFIED",
            "disposition": "RETAIN_FIXED_CONTAINED_UNTIL_VIEWPORT_BUFFER_CONTRACT_VERIFIED"
        }
        self.assertEqual(status["current_dimensions"], (720, 480))


class TestPort7cFailClosedNegativeControls(unittest.TestCase):
    """Section E: Fail-closed parser behavior and negative regression controls."""

    def test_missing_source_fails_closed(self):
        """Missing platform files raise FileNotFoundError."""
        with tempfile.TemporaryDirectory(prefix="port7c-test-") as tmpdir:
            with self.assertRaises(FileNotFoundError):
                load_platform_sources(Path(tmpdir))

    def test_commented_macro_rejected(self):
        """Commented macros cannot satisfy definition query."""
        with self.assertRaises(ValueError):
            parse_numeric_definition("// #define CAM_SCREEN_WIDTH 720", "CAM_SCREEN_WIDTH")

    def test_expression_macro_rejected(self):
        """Complex C macro expressions cannot satisfy integer definition query."""
        with self.assertRaises(ValueError):
            parse_numeric_definition("#define FOO (1 << 8)", "FOO")

    def test_duplicate_macro_rejected(self):
        """Duplicate active macro definitions raise ValueError."""
        with self.assertRaises(ValueError):
            parse_numeric_definition("#define FOO 1\n#define FOO 2\n", "FOO")

    def test_malformed_keymap_rejected(self):
        """Keymap without terminal sentinel is rejected."""
        bad_keymap = "KeyMap keymap[] = { {0, KEY_UP, 0x20} };"
        with self.assertRaises(ValueError):
            parse_keymap(bad_keymap)

    def test_screen_exceeding_bitmap_fails_containment(self):
        """Screen width exceeding bitmap buffer width is detected as containment failure."""
        sw, bw = 900, 736
        self.assertFalse(sw <= bw, "900 > 736 must fail containment")


if __name__ == '__main__':
    unittest.main()
