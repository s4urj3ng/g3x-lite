"""PORT-7B: clean-checkout reproducibility of the Playback KEYS_MASK0 correction.

chdk-port/ is an upstream CHDK r5491 checkout (21b9a14e) and the whole
platform/g3x directory is locally authored and Git-ignored (.gitignore:43), so
no bootstrap can recreate platform_kbd.h on a clean clone. This module makes
PORT-7B reproducible without tracking that tree:

* Tier 1 (clean clone, no skips): apply patches/0002-port7b-keys-mask0.patch
  to the committed preimage fixture with a strict, fuzz-free applier, check
  both SHA-256 values recorded in the patch header, then run the unchanged
  PORT-7A constant checks against the patched header plus verbatim excerpts of
  kbd.c, platform_camera.h and shooting.c (tests/fixtures/port7b/).
* Tier 2 (local workspace only, skipped when chdk-port/platform/g3x is absent):
  the live header must equal the patch postimage and every excerpt must still
  equal its recorded line range in the live source (stale-fixture guard).

Standard library only. No subprocess, compiler, ROM/binary read, or writes
outside a temporary directory. Hardware: STRICT NO-GO.

Run:
  python3 -B -m unittest discover -s tests -p test_port7b_reproducibility.py -v
Assemble a directory for the unmodified PORT-7A module:
  python3 -B tests/test_port7b_reproducibility.py --assemble DIR
  G3X_PLATFORM_DIR=DIR python3 -B -m unittest discover -s tests -p test_port7a_platform_configuration.py -v
"""

import hashlib
import os
from pathlib import Path
import re
import shutil
import sys
import tempfile
import unittest

import test_port7a_platform_configuration as port7a


REPO_ROOT = Path(__file__).resolve().parents[1]
PATCH = REPO_ROOT / "patches/0002-port7b-keys-mask0.patch"
FIXTURES = REPO_ROOT / "tests/fixtures/port7b"
PREIMAGE = FIXTURES / "platform_kbd.h.preimage"
LIVE_DIR = REPO_ROOT / "chdk-port/platform/g3x"
PATCH_TARGET = "platform/g3x/platform_kbd.h"

PRE_SHA = "4d2594313c304ffb6598d47cfc9cd4bbffd0f3b1b64d35e734df8e8218d459b0"
POST_SHA = "4c9fd8b4df5d8f45e65827eba5588b6bb2a145765764c0ef0baa85e668f49b24"
# Verbatim 1-based inclusive line ranges, copied from live sources whose
# SHA-256 values are recorded in PORT-7A section 8 (E7, E9, E10).
EXCERPTS = {
    "kbd.c": ((29, 45),),
    "platform_camera.h": ((18, 20), (73, 76)),
    "shooting.c": ((107, 126),),
}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def apply_unified_patch(original, patch_text, target=PATCH_TARGET):
    """Apply a single-file unified diff exactly; any mismatch raises ValueError."""
    lines = patch_text.splitlines()
    try:
        start = lines.index("--- a/" + target)
    except ValueError:
        raise ValueError(f"Patch has no --- a/{target} header") from None
    if lines[start + 1] != "+++ b/" + target:
        raise ValueError("Patch +++ header does not match target")
    if any(l.startswith("--- ") for l in lines[start + 2:]):
        raise ValueError("Patch touches more than one file")

    src = original.splitlines(keepends=True)
    out, pos, i = [], 0, start + 2
    while i < len(lines):
        m = re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@.*', lines[i])
        if not m:
            raise ValueError(f"Unexpected patch line: {lines[i]!r}")
        old_start, old_len = int(m[1]), int(m[2] or 1)
        new_len = int(m[4] or 1)
        hunk_pos = old_start - 1
        if hunk_pos < pos:
            raise ValueError("Overlapping or unordered hunks")
        out.extend(src[pos:hunk_pos])
        pos, i, old_seen, new_seen = hunk_pos, i + 1, 0, 0
        while i < len(lines) and not lines[i].startswith("@@"):
            tag, text = lines[i][:1], lines[i][1:]
            if tag in (" ", "-"):
                if pos >= len(src) or src[pos].rstrip("\n") != text:
                    raise ValueError(f"Hunk does not match preimage at line {pos + 1}")
                if tag == " ":
                    out.append(src[pos])
                pos, old_seen = pos + 1, old_seen + 1
                new_seen += tag == " "
            elif tag == "+":
                out.append(text + "\n")
                new_seen += 1
            else:
                raise ValueError(f"Unsupported hunk line: {lines[i]!r}")
            i += 1
        if (old_seen, new_seen) != (old_len, new_len):
            raise ValueError("Hunk line counts disagree with header")
    out.extend(src[pos:])
    return "".join(out)


def patch_header_sha(patch_text, label):
    found = re.findall(r'^# ' + label + r'\s+SHA-256:\s*([0-9a-f]{64})\s*$',
                       patch_text, flags=re.M)
    if len(found) != 1:
        raise ValueError(f"Expected one {label} SHA-256 in patch header")
    return found[0]


def assemble(dest):
    """Write the four PORT-7A inputs (patched header + excerpts) into dest."""
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    pre = PREIMAGE.read_bytes()
    if sha256(pre) != PRE_SHA:
        raise ValueError("Preimage fixture does not match recorded SHA-256")
    post = apply_unified_patch(pre.decode("utf-8"), PATCH.read_text(encoding="utf-8"))
    if sha256(post.encode("utf-8")) != POST_SHA:
        raise ValueError("Patched header does not match recorded postimage SHA-256")
    (dest / "platform_kbd.h").write_text(post, encoding="utf-8")
    for name in EXCERPTS:
        shutil.copyfile(FIXTURES / name, dest / name)
    return dest


class TestPatchAgainstCommittedBaseline(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.patch = PATCH.read_text(encoding="utf-8")
        cls.pre = PREIMAGE.read_text(encoding="utf-8")

    def test_header_records_the_fixture_preimage_and_postimage(self):
        self.assertEqual(patch_header_sha(self.patch, "Preimage"), PRE_SHA)
        self.assertEqual(patch_header_sha(self.patch, "Postimage"), POST_SHA)
        self.assertEqual(sha256(PREIMAGE.read_bytes()), PRE_SHA)

    def test_patch_reproduces_postimage(self):
        post = apply_unified_patch(self.pre, self.patch)
        self.assertEqual(sha256(post.encode("utf-8")), POST_SHA)

    def test_patch_changes_only_mask0_value_and_comments(self):
        post = apply_unified_patch(self.pre, self.patch)
        before = port7a.uncomment(self.pre).split()
        after = port7a.uncomment(post).split()
        self.assertEqual([t for t in before if t not in after], ['(0x000433F9)'])
        self.assertEqual([t for t in after if t not in before], ['(0x000533F9)'])
        self.assertEqual(port7a.override_masks(post), (0x000533F9, 0, 0))

    def test_reapplying_to_postimage_is_rejected(self):
        post = apply_unified_patch(self.pre, self.patch)
        with self.assertRaises(ValueError):
            apply_unified_patch(post, self.patch)

    def test_altered_preimage_is_rejected(self):
        with self.assertRaises(ValueError):
            apply_unified_patch(self.pre.replace("13 (Phone)", "13 (WiFi)"), self.patch)


class TestPort7aChecksOnPatchedFixture(port7a.TestRecordedGm110cConstants):
    """Runs every PORT-7A constant check against the assembled clean-clone inputs."""

    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="port7b-fixture-")
        cls.sources = port7a.load_sources(assemble(cls._tmp.name))
        cls.keys = port7a.keymap(cls.sources['kbd.c'])
        cls.camera = cls.sources['platform_camera.h']
        cls.header = cls.sources['platform_kbd.h']

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()


class TestPreimageFixtureShowsPlaybackGap(unittest.TestCase):
    def test_unpatched_header_leaves_playback_uncovered(self):
        keys = port7a.keymap((FIXTURES / "kbd.c").read_text(encoding="utf-8"))
        options = port7a.alt_options((FIXTURES / "platform_camera.h").read_text(encoding="utf-8"))
        masks = port7a.override_masks(PREIMAGE.read_text(encoding="utf-8"))
        self.assertEqual(port7a.alt_override_gaps(keys, options, masks),
                         {'KEY_PLAYBACK': 0x10000})


@unittest.skipUnless(all((LIVE_DIR / n).is_file() for n in ("platform_kbd.h", *EXCERPTS)),
                     "local chdk-port/platform/g3x sources not present (clean checkout)")
class TestLiveWorkspaceMatchesFixtures(unittest.TestCase):
    def test_live_header_is_patch_postimage(self):
        live = sha256((LIVE_DIR / "platform_kbd.h").read_bytes())
        self.assertNotEqual(live, PRE_SHA, "Live header is unpatched; apply patch 0002")
        self.assertEqual(live, POST_SHA)

    def test_excerpts_match_live_line_ranges(self):
        for name, ranges in EXCERPTS.items():
            with self.subTest(name=name):
                live = (LIVE_DIR / name).read_text(encoding="utf-8").splitlines(keepends=True)
                expected = "".join("".join(live[a - 1:b]) for a, b in ranges)
                self.assertEqual((FIXTURES / name).read_text(encoding="utf-8"), expected)


if __name__ == "__main__":
    if len(sys.argv) == 3 and sys.argv[1] == "--assemble":
        print(assemble(os.path.abspath(sys.argv[2])))
    else:
        unittest.main()
