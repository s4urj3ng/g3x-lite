"""Offline checks of the actual PORT-46 diagnostic and both pinned-toolchain builds."""

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
HEADER = ROOT / "chdk-port/platform/g3x/kbd_check.h"
OUT = ROOT / "out/port46-test"
NM = ROOT / "toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-nm"
MANIFEST = ROOT / "manifests/port46_kbd_check_manifest.json"

# Independent oracle: PORT46_KEYMAP.md FINSIG rows and physw_bits.txt events.
# Composite FULL must precede HALF and FULL_ONLY in CHDK's first-match decoder.
EXPECTED_KEYS = [
    (0, "KEY_SHOOT_FULL", 0x00040001),
    (0, "KEY_SHOOT_HALF", 0x00040000),
    (0, "KEY_SHOOT_FULL_ONLY", 0x00000001),
    (0, "KEY_VIDEO", 0x00000008),
    (0, "KEY_MENU", 0x00000010),
    (0, "KEY_UP", 0x00000020),
    (0, "KEY_DOWN", 0x00000040),
    (0, "KEY_RIGHT", 0x00000080),
    (0, "KEY_LEFT", 0x00000100),
    (0, "KEY_SET", 0x00000200),
    (0, "KEY_DISPLAY", 0x00001000),
    (0, "KEY_WIFI", 0x00002000),
    (0, "KEY_PLAYBACK", 0x00010000),
    (0, "KEY_POWER", 0x00020000),
]
EXPECTED_EVENTS = {
    0: 0x01, 3: 0x02, 4: 0x14, 5: 0x06, 6: 0x07, 7: 0x09,
    8: 0x08, 9: 0x0a, 12: 0x0d, 13: 0x103, 16: 0x101,
    17: 0x100, 18: 0x00,
}


def read_keymap(path):
    table = re.search(r"KeyMap keymap\[\] = \{.*?\n\};", path.read_text(), re.S)
    if table is None:
        raise AssertionError(f"Missing keymap in {path}")
    return [(int(word), key, int(mask, 16)) for word, key, mask in re.findall(
        r"\{\s*(\d+),\s*(KEY_\w+)\s*,\s*(0x[0-9a-fA-F]+)\s*\}", table[0])]


def read_masks(path):
    text = subprocess.check_output([
        "cc", "-E", "-dM", "-DG3X_KBD_CHECK=1", "-DG3X_GUI_DBUF=1",
        "-x", "c", str(path),
    ], text=True)
    return [int(re.search(rf"^#define KEYS_MASK{i} \((0x[0-9a-fA-F]+)\)$",
                          text, re.M)[1], 16) for i in range(3)]


def distribution_snapshot(path):
    files = [path / "DISKBOOT.BIN", *sorted((path / "CHDK").rglob("*"))]
    if not (path / "CHDK").is_dir():
        raise AssertionError(f"Missing CHDK distribution: {path}")
    return {p.relative_to(path).as_posix(): {
        "size": p.stat().st_size, "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
    } for p in files if p.is_file()}


class TestPort46KeymapModel(unittest.TestCase):
    def test_documented_finsig_bits_decode_to_expected_keys(self):
        doc = (ROOT / "docs/PORT46_KEYMAP.md").read_text().split("## Masks")[0]
        rows = [line.split("|") for line in doc.splitlines() if line.startswith("| KEY_")]
        verified = [row for row in rows if row[5].strip() == "FINSIG"]
        self.assertEqual(len(verified), len(EXPECTED_KEYS))
        documented = []
        for row in verified:
            key = re.search(r"KEY_\w+", row[1])[0]
            word, first_bit = map(int, re.search(r"w(\d+)\.b(\d+)", row[3]).groups())
            bits = [first_bit, *map(int, re.findall(r"\+b(\d+)", row[3]))]
            documented.append((word, key, sum(1 << bit for bit in bits)))
        self.assertEqual(documented, EXPECTED_KEYS)

        finsig = (ROOT / "reference/finsig_gm110c/physw_bits.txt").read_text()
        events = {(int(word), int(mask, 16)): int(event, 16)
                  for event, word, mask in re.findall(
                      r"^0x\w+\s+0x\w+\s+(0x\w+)\s+(\d+)\s+(0x\w+)\s+[01]$",
                      finsig, re.M)}
        for bit, event in EXPECTED_EVENTS.items():
            self.assertEqual(events[(0, 1 << bit)], event)

        for source in [ROOT / "chdk-port/platform/g3x/kbd.c", ROOT / "full_build/g3x/kbd.c"]:
            actual = read_keymap(source)
            self.assertEqual(actual, EXPECTED_KEYS)
            for word, expected, mask in EXPECTED_KEYS:
                with self.subTest(source=source, key=expected):
                    state = [0xffffffff] * 3
                    state[word] &= ~mask
                    decoded = next((key for group, key, bits in actual
                                    if state[group] & bits == 0), "none")
                    self.assertEqual(decoded, expected)
            # Historical candidates have events, but no verified physical key names.
            for row in (row for row in rows if row[5].strip() == "HISTORICAL_CHDK"):
                word, bit = map(int, re.search(r"w(\d+)\.b(\d+)", row[3]).groups())
                self.assertIn((word, 1 << bit), events)
                state = [0xffffffff] * 3
                state[word] &= ~(1 << bit)
                self.assertFalse(any(state[g] & mask == 0 for g, _, mask in actual))

    def test_kbd_check_masks_cover_override_keys_and_preserve_power_passthrough(self):
        """Literal all-key coverage is contradicted by the documented Power policy."""
        for base in [ROOT / "chdk-port/platform/g3x", ROOT / "full_build/g3x"]:
            masks = read_masks(base / "platform_kbd.h")
            self.assertEqual(masks, [0x000533f9, 0, 0])
            uncovered = [(word, key, bits & ~masks[word])
                         for word, key, bits in read_keymap(base / "kbd.c")
                         if bits & ~masks[word]]
            self.assertEqual(uncovered, [(0, "KEY_POWER", 0x00020000)])
            for word, key, bits in EXPECTED_KEYS:
                if key != "KEY_POWER":
                    self.assertEqual(bits & masks[word], bits, key)


class TestPort46HostDiagnostic(unittest.TestCase):
    def test_actual_decoder_and_draw_with_alt_on_and_off(self):
        """Exercise all mappings, shutter precedence, release padding and raw word order."""
        kbd = (ROOT / "chdk-port/platform/g3x/kbd.c").read_text()
        keymap = re.search(r"KeyMap keymap\[\] = \{.*?\n\};", kbd, re.S).group()
        common = (ROOT / "chdk-port/core/kbd_common.c").read_text()
        decoder = re.search(r"long kbd_get_pressed_key\(\)\n\{.*?\n\}", common, re.S).group()
        cases = re.findall(r"\{ 0, (KEY_\w+)\s*,(0x[0-9A-Fa-f]+) \}", keymap)
        self.assertEqual(len(cases), 14)
        vectors = "\n".join(
            f'    check_key({mask}u, "{name}");' for name, mask in cases
        )
        source = r'''
#include <assert.h>
#include <stdio.h>
#include <string.h>
#include "keyboard.h"
#define G3X_KBD_CHECK 1
#define G3X_GUI_DBUF 1
#define FONT_WIDTH 16
#define FONT_HEIGHT 32
#define COLOR_BLACK 0
#define COLOR_WHITE 1
#define MAKE_COLOR(bg, fg) (((bg) << 8) | (fg))
struct { struct { int gui_mode_alt; } state; } camera_info;
struct { int width, height; } camera_screen = {900, 600};
volatile long physw_status[3];
long kbd_new_state[3];
typedef struct { int grp; long hackkey; unsigned int canonkey; } KeyMap;
KEYMAP
DECODER
static int samples, draws;
static char last_line[47];
static long sample_key(void) { ++samples; return kbd_get_pressed_key(); }
#define kbd_get_pressed_key sample_key
static void draw_string(int x, int y, const char *s, int color)
{
    assert(x == 82 && y == 504);
    assert(x + 46 * FONT_WIDTH <= 890 && y + FONT_HEIGHT <= 588);
    assert(color == MAKE_COLOR(COLOR_BLACK, COLOR_WHITE));
    assert(strlen(s) == 46);
    strcpy(last_line, s);
    ++draws;
}
#include "kbd_check.h"
static void check_key(unsigned int mask, const char *name)
{
    kbd_new_state[0] = 0xffffffffu & ~mask;
    int old_draws = draws, old_samples = samples;
    gui_kbd_check_draw();
    assert(draws == old_draws + 1 && samples == old_samples + 1);
    char expected[47];
    snprintf(expected, sizeof(expected), "%-19s %08x %08x %08x", name,
             (unsigned int)physw_status[0], (unsigned int)physw_status[1],
             (unsigned int)physw_status[2]);
    assert(strcmp(last_line, expected) == 0);
}
int main(void)
{
    physw_status[0] = 0xffffffffu;
    physw_status[1] = 0x01234567u;
    physw_status[2] = 0x89abcdefu;
    /* ALT off performs no decoder calls and no draw writes. */
    for (int i = 0; i < 20; ++i) gui_kbd_check_draw();
    assert(samples == 0 && draws == 0);
    camera_info.state.gui_mode_alt = 1;
VECTORS
    /* Composite shutter wins over HALF/FULL_ONLY in the real common decoder. */
    check_key(0x00040001u, "KEY_SHOOT_FULL");
    check_key(0, "none");
    assert(strcmp(last_line, "none                ffffffff 01234567 89abcdef") == 0);
    physw_status[0] = physw_status[1] = physw_status[2] = 0;
    check_key(0, "none");
    camera_info.state.gui_mode_alt = 0;
    int old_draws = draws, old_samples = samples;
    gui_kbd_check_draw();
    assert(draws == old_draws && samples == old_samples);
    return 0;
}
'''.replace("KEYMAP", keymap).replace("DECODER", decoder).replace("VECTORS", vectors)
        OUT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=OUT) as td:
            cfile = Path(td) / "diagnostic.c"
            exe = Path(td) / "diagnostic"
            cfile.write_text(source)
            result = subprocess.run([
                "cc", "-std=c99", "-Wall", "-Wextra", "-Werror", "-fstack-protector-all",
                "-I", str(HEADER.parent), "-idirafter", str(ROOT / "chdk-port/include"),
                str(cfile), "-o", str(exe),
            ], capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            subprocess.run([str(exe)], check=True, capture_output=True, text=True)

    def test_dependency_rejects_missing_dbuf(self):
        result = subprocess.run([
            "cc", "-E", "-DG3X_KBD_CHECK=1", "-x", "c", str(HEADER),
        ], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires G3X_GUI_DBUF=1", result.stderr)
        result = subprocess.run([
            "make", "-f", "chdk-port/platform/g3x/Makefile", "G3X_KBD_CHECK=1",
        ], cwd=ROOT, capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("requires G3X_GUI_DBUF=1", result.stderr)


class TestPort46Builds(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        OUT.mkdir(parents=True, exist_ok=True)
        cls.variants = []
        cls.repeats = {}
        cls.guard_variants = []
        for name, extra in [("dbuf", []), ("no-overdraw", ["--no-overdraw"])]:
            env = os.environ.copy()
            for flag in ["G3X_GUI_FIX", "G3X_GUI_DBUF", "G3X_GUI_NOOVERDRAW", "FULL_HOOKS", "MAKEFLAGS"]:
                env.pop(flag, None)
            # Exercise the environment opt-in as well as explicit DBUF dependency propagation.
            env["G3X_KBD_CHECK"] = "1"
            env["MAKEFLAGS"] = f"CC={ROOT / 'scripts/gcc_deterministic_wrapper.sh'}"
            if extra:
                env["G3X_GUI_NOOVERDRAW"] = "1"
            for suffix in ["", "-repeat"]:
                path = OUT / (name + suffix)
                with (OUT / (name + suffix + ".log")).open("w") as log:
                    subprocess.run([
                        sys.executable, "-B", str(ROOT / "scripts/build_port43_dbuf.py"),
                        "--out-dir", str(path), *extra,
                    ], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
                cls.guard_variants.append(path)
            cls.variants.append(OUT / name)
            cls.repeats[name] = OUT / (name + "-repeat")
            # FULL_HOOKS also composes with each diagnostic variant. Check its ELF,
            # without assigning a new distribution pin beyond the requested pair.
            path = OUT / (name + "-full-hooks")
            with (OUT / (path.name + ".log")).open("w") as log:
                subprocess.run([
                    sys.executable, "-B", str(ROOT / "scripts/build_port43_dbuf.py"),
                    "--out-dir", str(path), "--full-hooks", *extra,
                ], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            cls.guard_variants.append(path)

    def test_clean_builds_are_byte_identical_and_match_pinned_manifest(self):
        pinned = json.loads(MANIFEST.read_text())
        self.assertEqual(set(pinned["variants"]), {"dbuf", "no-overdraw"})
        gcc = NM.with_name("arm-none-eabi-gcc")
        self.assertEqual(hashlib.sha256(gcc.read_bytes()).hexdigest(),
                         pinned["verification"]["compiler_sha256"])
        self.assertEqual(hashlib.sha256((ROOT / "scripts/gcc_deterministic_wrapper.sh").read_bytes()).hexdigest(),
                         pinned["verification"]["deterministic_wrapper_sha256"])
        for path in self.variants:
            with self.subTest(variant=path.name):
                record = pinned["variants"][path.name]
                generated = json.loads((path / "port46_kbd_check_manifest.json").read_text())
                self.assertEqual(generated, {k: record[k] for k in ("build", "artifacts")})
                self.assertEqual(record["build"]["toolchain"], "gcc-arm-none-eabi-5_4-2016q3")
                self.assertEqual(record["reproducibility"]["clean_builds"], 2)
                first = distribution_snapshot(path)
                repeat = self.repeats[path.name]
                self.assertEqual(first, distribution_snapshot(repeat))
                expected = dict(record["artifacts"]["chdk_files"])
                expected["DISKBOOT.BIN"] = {
                    k: record["artifacts"]["DISKBOOT.BIN"][k] for k in ("size", "sha256")}
                self.assertEqual(first, expected)
                self.assertEqual(record["artifacts"]["chdk_files_count"], len(first) - 1)
                for relative in first:
                    self.assertEqual((path / relative).read_bytes(),
                                     (repeat / relative).read_bytes(), relative)

    def test_builds_have_diagnostic_and_pass_end_guard(self):
        for path in self.guard_variants:
            with self.subTest(variant=path.name):
                manifest = json.loads((path / "port46_kbd_check_manifest.json").read_text())
                self.assertIn("G3X_KBD_CHECK=1", manifest["build"]["flags"])
                self.assertIn("G3X_GUI_DBUF=1", manifest["build"]["flags"])
                self.assertEqual("G3X_GUI_NOOVERDRAW=1" in manifest["build"]["flags"],
                                 path.name.startswith("no-overdraw"))
                stage = path / "stage_chdk"
                elf = stage / "platform/g3x/sub/110c/main.elf"
                symbols = subprocess.check_output([str(NM), "-S", str(elf)], text=True)
                end = re.search(r"^([0-9a-f]+) B _end$", symbols, re.M)
                self.assertIsNotNone(end)
                self.assertLessEqual(int(end[1], 16), 0x003687B0 + 65536)
                self.assertRegex(symbols, r" T gui_kbd_check_draw\b")
                for row in symbols.splitlines():
                    fields = row.split()
                    if len(fields) == 4 and fields[2] in "bBdD":
                        self.assertLessEqual(int(fields[1], 16), 65536, row)
                # The actual GUI object adds no writable diagnostic state or allocator calls.
                obj = stage / "platform/g3x/sub/110c/gui.thm.o"
                objsymbols = subprocess.check_output([str(NM), "-S", str(obj)], text=True)
                self.assertNotRegex(objsymbols, r"[bBdD] .*kbd_check")
                source = (stage / "platform/g3x/kbd_check.h").read_text()
                self.assertNotRegex(source, r"\b(?:malloc|calloc|realloc|static)\b")

    def test_real_redraw_and_idle_hooks_and_unchanged_keymaps(self):
        for path in self.variants:
            with self.subTest(variant=path.name):
                stage = path / "stage_chdk"
                gui = (stage / "core/gui.c").read_text()
                main = (stage / "core/main.c").read_text()
                self.assertIn('include "../platform/g3x/kbd_check.h"', gui)
                self.assertIn("    console_draw(force_redraw);\n#if defined(G3X_KBD_CHECK)", gui)
                self.assertIn("else if (camera_info.state.gui_mode_alt)", main)
                self.assertIn("gui_kbd_check_draw();", main)
                self.assertIn("#define FONT_WIDTH              16", (stage / "core/gui_draw.h").read_text())
                original = (ROOT / "chdk-port/platform/g3x/kbd.c").read_text()
                built = (stage / "platform/g3x/kbd.c").read_text()
                pattern = r"KeyMap keymap\[\] = \{.*?\n\};"
                self.assertEqual(re.search(pattern, original, re.S).group(),
                                 re.search(pattern, built, re.S).group())
                self.assertEqual((stage / "platform/g3x/platform_kbd.h").read_bytes(),
                                 (ROOT / "chdk-port/platform/g3x/platform_kbd.h").read_bytes())
                self.assertEqual(read_keymap(stage / "platform/g3x/kbd.c"), EXPECTED_KEYS)
                self.assertEqual(read_masks(stage / "platform/g3x/platform_kbd.h"), [0x000533f9, 0, 0])
