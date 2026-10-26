"""PORT-7A: source-only GM1.10C configuration regression checks.

No firmware/ROM reads, compiler, subprocess, existing validator imports or hooks.
Run only this module, not repository-wide discovery:
  python3 -B -m unittest discover -s tests -p test_port7a_platform_configuration.py -v

Evidence (local retrieval 2026-10-26):
* docs/UI001B1_HARDWARE_RESULT.md section 3.1: eight owner-reported differences.
* docs/CHDK_PORT0_CODEX_REVIEW.md section 7: independent recorded GM1.10C
  switch-table assignments, four ancillary flags, and 17 mode-ID memberships.
* docs/CHDK_PORT0C_CODEX_INCREMENTAL_REVIEW.md section 6: same boundaries.
* docs/PORT7A_PLATFORM_CONFIGURATION_VALIDATION.md: identities and limitations.

Numeric mode membership does NOT verify the MODE_* labels. Recorded switch
positions do NOT verify interception, unsampled physical keys or runtime safety.
Geometry checks establish relationships only; no surface dimensions are pinned.
The historical E patch and generated physw dump are not test dependencies.

PORT-7B applied the Playback ALT override correction (KEYS_MASK0 0x000433F9 ->
0x000533F9, docs/PORT7B_PLAYBACK_MASK_CORRECTION.md). ALT coverage is now a
normal test; the mask is pinned so Power (bit 17) stays excluded.
Missing required platform sources fail closed (no skips or fallback fixtures).
G3X_PLATFORM_DIR optionally selects a separately supplied source-only directory.
On a clean clone (platform/g3x is Git-ignored) use test_port7b_reproducibility.py,
or its --assemble DIR output as G3X_PLATFORM_DIR.
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

# These are literal evidence expectations, not values derived from current code.
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
RECORDED_STATIC_KEYS = {
    "KEY_SET": (0, 0x200),
    "KEY_SHOOT_HALF": (0, 0x40000),
    "KEY_SHOOT_FULL_ONLY": (0, 0x1),
    "KEY_SHOOT_FULL": (0, 0x40001),
    "KEY_PLAYBACK": (0, 0x10000),
    "KEY_POWER": (0, 0x20000),
}
ANCILLARY = {
    "SD_READONLY": (1, 0x20000000),
    "USB": (2, 0x00800000),
    "BATTCOVER": (2, 0x00400000),
    "HOTSHOE": (1, 0x00001000),
}
# Dossier confirms membership of all 17 current IDs, not name-to-value semantics.
RECORDED_MODE_IDS = frozenset({
    32768, 32770, 32771, 32772, 32773, 33299, 33298,
    2643, 2650, 2651, 2652, 16406, 16416, 16453, 16454, 16459, 16953,
})


def uncomment(text):
    """Preserve quoted strings; remove comments before matching active data."""
    pattern = r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*'
    return re.sub(pattern, lambda m: m[0] if m[0].startswith('"') else ' ',
                  text, flags=re.S)


def load_sources(root):
    """Read exactly four ordinary source files; missing input is an error."""
    return {name: (root / name).read_text(encoding="utf-8") for name in (
        "platform_camera.h", "platform_kbd.h", "kbd.c", "shooting.c"
    )}


def definition(text, name):
    values = re.findall(r'^\s*#define\s+' + re.escape(name) + r'\s+([^\n]+)',
                        uncomment(text), flags=re.M)
    if len(values) != 1:
        raise ValueError(f"Expected one active {name} definition, got {len(values)}")
    return values[0].strip()


def number_definition(text, name):
    # Deliberately accepts a single numeric literal, not arbitrary C expressions.
    value = definition(text, name).strip('() \t')
    if not re.fullmatch(r'0[xX][0-9a-fA-F]+|[0-9]+', value):
        raise ValueError(f"Unsupported numeric definition {name}: {value}")
    return int(value, 0)


def array_rows(text, type_name, name):
    matches = re.findall(r'\b' + type_name + r'\s+' + name
                         + r'\s*\[\s*\]\s*=\s*\{(.*?)\};',
                         uncomment(text), flags=re.S)
    if len(matches) != 1:
        raise ValueError(f"Expected one {name} array")
    body = matches[0]
    rows = re.findall(r'\{([^{}]+)\}', body)
    if not rows or re.sub(r'\{[^{}]+\}|[\s,]', '', body):
        raise ValueError(f"Unsupported or empty {name} initializer")
    return [tuple(field.strip() for field in row.split(',')) for row in rows]


def keymap(text):
    rows = array_rows(text, 'KeyMap', 'keymap')
    if rows[-1] != ('0', '0', '0'):
        raise ValueError("Missing terminal zero keymap sentinel")
    result = {}
    for row in rows[:-1]:
        if len(row) != 3:
            raise ValueError("Invalid keymap row")
        group, key, mask = row
        if not re.fullmatch(r'KEY_[A-Z0-9_]+', key) or key in result:
            raise ValueError(f"Invalid/duplicate key {key}")
        group, mask = int(group, 0), int(mask, 0)
        if not 0 <= group < 3 or not 0 < mask <= 0xFFFFFFFF:
            raise ValueError(f"Invalid key group/mask: {key}")
        result[key] = (group, mask)
    return result


def override_masks(header):
    return tuple(number_definition(header, f'KEYS_MASK{i}') for i in range(3))


def alt_options(camera):
    value = definition(camera, 'CAM_ALT_BUTTON_OPTIONS')
    if not re.fullmatch(r'\{\s*KEY_[A-Z0-9_]+(?:\s*,\s*KEY_[A-Z0-9_]+)*\s*\}', value):
        raise ValueError("Unsupported ALT initializer")
    return re.findall(r'KEY_[A-Z0-9_]+', value)


def alt_override_gaps(keys, options, masks):
    return {key: (keys[key][1] & ~masks[keys[key][0]])
            for key in options
            if keys[key][1] & ~masks[keys[key][0]]}


def assert_evidence(keys, evidence):
    for key, expected in evidence.items():
        if keys.get(key) != expected:
            raise ValueError(f"{key}: {keys.get(key)} differs from recorded {expected}")


def geometry_fits(camera):
    sw, sh, bw, bh = (number_definition(camera, key) for key in (
        'CAM_SCREEN_WIDTH', 'CAM_SCREEN_HEIGHT', 'CAM_BITMAP_WIDTH', 'CAM_BITMAP_HEIGHT'
    ))
    return 0 < sw <= bw and 0 < sh <= bh


class TestRecordedGm110cConstants(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = load_sources(PLATFORM_DIR)
        cls.keys = keymap(cls.sources['kbd.c'])
        cls.camera = cls.sources['platform_camera.h']
        cls.header = cls.sources['platform_kbd.h']

    def test_eight_observed_key_assignments(self):
        assert_evidence(self.keys, OBSERVED_KEYS)

    def test_six_recorded_static_key_assignments(self):
        assert_evidence(self.keys, RECORDED_STATIC_KEYS)

    def test_four_recorded_ancillary_flag_pairs(self):
        for prefix, (index, mask) in ANCILLARY.items():
            with self.subTest(prefix=prefix):
                self.assertEqual(number_definition(self.header, prefix + '_IDX'), index)
                suffix = '_MASK' if prefix == 'USB' else '_FLAG'
                self.assertEqual(number_definition(self.header, prefix + suffix), mask)

    def test_shutter_composite_and_full_before_half(self):
        half, full, only = (self.keys[name][1] for name in (
            'KEY_SHOOT_HALF', 'KEY_SHOOT_FULL', 'KEY_SHOOT_FULL_ONLY'
        ))
        self.assertEqual(full, half | only)
        names = list(self.keys)
        self.assertLess(names.index('KEY_SHOOT_FULL'), names.index('KEY_SHOOT_HALF'))

    def test_override_covers_observed_keys(self):
        masks = override_masks(self.header)
        for key, (group, mask) in OBSERVED_KEYS.items():
            with self.subTest(key=key):
                self.assertEqual(mask & ~masks[group], 0)

    def test_alt_option_names_and_mappings_are_consistent(self):
        names = re.findall(r'"([^"\n]*)"', definition(self.camera, 'CAM_ALT_BUTTON_NAMES'))
        options = alt_options(self.camera)
        self.assertEqual(len(names), len(options))
        self.assertEqual(len(options), len(set(options)))
        self.assertTrue(set(options) <= self.keys.keys())

    def test_alt_options_have_override_coverage(self):
        self.assertEqual(alt_override_gaps(
            self.keys, alt_options(self.camera), override_masks(self.header)), {})

    def test_playback_correction_is_minimal_and_excludes_power(self):
        masks = override_masks(self.header)
        self.assertEqual(masks, (0x000533F9, 0, 0))
        self.assertEqual(masks[0] ^ 0x000433F9, RECORDED_STATIC_KEYS['KEY_PLAYBACK'][1])
        self.assertEqual(masks[0] & RECORDED_STATIC_KEYS['KEY_POWER'][1], 0)

    def test_previous_mask_reproduces_playback_gap(self):
        previous = (0x000433F9, 0, 0)
        self.assertEqual(alt_override_gaps(self.keys, alt_options(self.camera), previous),
                         {'KEY_PLAYBACK': 0x10000})

    def test_current_mode_numbers_have_recorded_membership(self):
        rows = array_rows(self.sources['shooting.c'], 'CapturemodeMap', 'modemap')
        self.assertTrue(all(len(row) == 2 for row in rows))
        numbers = [int(row[1], 0) for row in rows]
        self.assertEqual(len(numbers), len(set(numbers)))
        self.assertEqual(frozenset(numbers), RECORDED_MODE_IDS)

    def test_geometry_is_internally_contained_only(self):
        self.assertTrue(geometry_fits(self.camera))


class TestFailClosedAndNegativeControls(unittest.TestCase):
    def test_missing_platform_sources_are_errors(self):
        with tempfile.TemporaryDirectory(prefix='port7a-missing-') as folder:
            with self.assertRaises(FileNotFoundError):
                load_sources(Path(folder))

    def test_comments_cannot_supply_a_definition(self):
        with self.assertRaises(ValueError):
            number_definition('// #define KEYS_MASK0 0x433f9', 'KEYS_MASK0')

    def test_duplicate_and_expression_definitions_are_rejected(self):
        for source in ('#define MASK 1\n#define MASK 2', '#define MASK (1 << 2)'):
            with self.subTest(source=source), self.assertRaises(ValueError):
                number_definition(source, 'MASK')

    def test_changed_or_swapped_observed_assignments_are_rejected(self):
        changed = dict(OBSERVED_KEYS)
        changed['KEY_UP'], changed['KEY_DOWN'] = changed['KEY_DOWN'], changed['KEY_UP']
        with self.assertRaises(ValueError):
            assert_evidence(changed, OBSERVED_KEYS)

    def test_missing_observed_key_is_rejected(self):
        changed = dict(OBSERVED_KEYS)
        del changed['KEY_MENU']
        with self.assertRaises(ValueError):
            assert_evidence(changed, OBSERVED_KEYS)

    def test_truncated_or_duplicate_keymap_is_rejected(self):
        for source in (
            'KeyMap keymap[] = {{0,KEY_UP,0x20}};',
            'KeyMap keymap[] = {{0,KEY_UP,0x20},{0,KEY_UP,0x40},{0,0,0}};',
        ):
            with self.subTest(source=source), self.assertRaises(ValueError):
                keymap(source)

    def test_display_width_change_without_buffer_change_is_rejected(self):
        source = ('#define CAM_SCREEN_WIDTH 900\n#define CAM_SCREEN_HEIGHT 480\n'
                  '#define CAM_BITMAP_WIDTH 736\n#define CAM_BITMAP_HEIGHT 480\n')
        self.assertFalse(geometry_fits(source))


if __name__ == '__main__':
    unittest.main()
