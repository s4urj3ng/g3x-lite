"""Offline checks of the actual PORT-46 diagnostic and both pinned-toolchain builds."""

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
        for name, extra in [("dbuf", []), ("no-overdraw", ["--no-overdraw"])]:
            path = OUT / name
            env = os.environ.copy()
            for flag in ["G3X_GUI_FIX", "G3X_GUI_DBUF", "G3X_GUI_NOOVERDRAW", "FULL_HOOKS"]:
                env.pop(flag, None)
            # Exercise the environment opt-in as well as explicit DBUF dependency propagation.
            env["G3X_KBD_CHECK"] = "1"
            with (OUT / (name + ".log")).open("w") as log:
                subprocess.run([
                    sys.executable, "-B", str(ROOT / "scripts/build_port43_dbuf.py"),
                    "--out-dir", str(path), *extra,
                ], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT, check=True)
            cls.variants.append(path)

    def test_builds_have_diagnostic_and_pass_end_guard(self):
        for path in self.variants:
            with self.subTest(variant=path.name):
                manifest = json.loads((path / "port46_kbd_check_manifest.json").read_text())
                self.assertIn("G3X_KBD_CHECK=1", manifest["build"]["flags"])
                self.assertIn("G3X_GUI_DBUF=1", manifest["build"]["flags"])
                self.assertEqual("G3X_GUI_NOOVERDRAW=1" in manifest["build"]["flags"],
                                 path.name == "no-overdraw")
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
