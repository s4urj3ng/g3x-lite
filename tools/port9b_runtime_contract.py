#!/usr/bin/env python3
"""PORT-9B: offline integration contract between PORT-8A sources and PORT-9A.

Checks that the bootstrapped GM1.10C platform sources (PORT-8A) and the
tracked boot prototype agree with the runtime lifecycle model (PORT-9A):

  C1 integrity  every manifest file is present and at its final SHA-256
                (PORT-8A build_expected / MANIFEST.json);
  C2 config     configuration the runtime interfaces rely on (DryOS platform,
                ALT button inside KEYS_MASK0, Power excluded);
  C3 interfaces no runtime interface is active in source beyond what the
                PORT-9A preconditions allow (source must not run ahead of
                evidence);
  C4 policy     preconditions are the GM1.10C defaults (all unverified);
                anything else is refused unless explicitly allowed, and is
                then reported as HYPOTHETICAL, never VERIFIED;
  C5 registry   unverified firmware runtime facts are listed, address-free.

Labels: VERIFIED_SOURCE = a property of the checked source text;
UNVERIFIED_RUNTIME = a firmware runtime fact this tool cannot establish;
HYPOTHETICAL = a result computed under preconditions that are not evidence.

Without --target the sources are rebuilt in memory from vendor/ and the
patches (nothing is written). With --target the tree is only read.
Standard library only. No subprocess, compiler, ROM, network or hardware.

Exit codes: 0 contract holds, 1 contract violation, 3 integrity error.

Usage:
  python3 -B tools/port9b_runtime_contract.py [--target CHDK_ROOT]
"""

import argparse
from dataclasses import dataclass, fields
from pathlib import Path, PurePosixPath
import re
import sys

TOOLS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(TOOLS_DIR))

import bootstrap_chdk_platform as boot  # noqa: E402
import port9a_runtime_lifecycle as rt  # noqa: E402


REPO_ROOT = boot.REPO_ROOT
PROTOTYPE = "platform/g3x/sub/110c/boot_prototype.c"

VERIFIED_SOURCE = "VERIFIED_SOURCE"
UNVERIFIED_RUNTIME = "UNVERIFIED_RUNTIME"
HYPOTHETICAL = "HYPOTHETICAL"

KEY_POWER_BIT = 0x00020000

# Firmware runtime facts the integration needs and nobody has verified for
# GM1.10C (PORT-9A map section 5). No addresses on purpose: a value only
# enters here once it is ROM-verified for GM1.10C, never from GM1.10E.
UNVERIFIED_RUNTIME_FACTS = (
    ("U1", "create_task_prologue_verified",
     "CreateTask prologue bytes and the literal replayed after it"),
    ("U2", "init_file_modules_entry_verified",
     "task_InitFileModules entry and its success/failure semantics"),
    ("U3", "physw_entry_verified",
     "task_PhySw entry independent of GM1.10E; role of the PhySw creator call"),
    ("U4", None, "SpyTask creation point and priority on GM1.10C"),
)


class ContractError(Exception):
    pass


@dataclass(frozen=True)
class Finding:
    check: str
    label: str
    ok: bool
    detail: str


# -- source parsing ----------------------------------------------------------

def strip_c_comments(text):
    """Blank C comments, keeping string literals (inline asm lives in them)."""
    pattern = r'"(?:\\.|[^"\\])*"|/\*.*?\*/|//[^\n]*'
    return re.sub(pattern, lambda m: m[0] if m[0].startswith('"') else " ",
                  text, flags=re.S)


def define(text, name):
    values = re.findall(r'^\s*#define\s+' + re.escape(name) + r'(?:\s+([^\n]*))?$',
                        strip_c_comments(text), flags=re.M)
    if len(values) != 1:
        raise ContractError(f"expected one active #define {name}, found {len(values)}")
    return values[0].strip()


def numeric_define(text, name):
    raw = define(text, name).strip("() \t")
    if not re.fullmatch(r"0[xX][0-9a-fA-F]+|[0-9]+", raw):
        raise ContractError(f"{name} is not a numeric literal: {raw!r}")
    return int(raw, 0)


def keymap(kbd_text):
    body = re.findall(r'\bKeyMap\s+keymap\s*\[\s*\]\s*=\s*\{(.*?)\};',
                      strip_c_comments(kbd_text), flags=re.S)
    if len(body) != 1:
        raise ContractError("expected one KeyMap keymap[] initializer")
    rows = [tuple(f.strip() for f in r.split(","))
            for r in re.findall(r'\{([^{}]+)\}', body[0])]
    if not rows or rows[-1] != ("0", "0", "0"):
        raise ContractError("keymap lacks the {0, 0, 0} sentinel")
    result = {}
    for group, key, mask in rows[:-1]:
        if key in result:
            raise ContractError(f"duplicate keymap entry {key}")
        result[key] = (int(group, 0), int(mask, 0))
    return result


def defines_function(text, name):
    """True if `name` has a function definition (a body) in active code."""
    return re.search(r'\b' + re.escape(name) + r'\s*\([^;{)]*\)\s*\{',
                     strip_c_comments(text)) is not None


def mentions(text, name):
    return re.search(r'\b' + re.escape(name) + r'\b', strip_c_comments(text)) is not None


def asm_calls(text, target):
    """True if active inline asm contains a branch-with-link to `target`."""
    return re.search(r'"\s*blx?\s+' + re.escape(target) + r'\b',
                     strip_c_comments(text)) is not None


# -- source loading ----------------------------------------------------------

def load_sources(target_root=None, manifest_path=boot.DEFAULT_MANIFEST,
                 repo_root=REPO_ROOT):
    """Return ({relpath: text}, origin). Never writes.

    The vendored baseline and patches are always integrity-checked through
    PORT-8A. With target_root, every manifest file there must be a regular
    file at its final hash; without it the final bytes are taken from memory.
    """
    try:
        manifest = boot.load_manifest(manifest_path)
        expected = boot.build_expected(manifest, manifest_path, repo_root)
    except (boot.IntegrityError, OSError, UnicodeDecodeError) as exc:
        raise ContractError(f"integrity: {exc}") from None

    sources = {}
    if target_root is None:
        origin = "in-memory (vendor + patches)"
        for rel, (_, final) in expected.items():
            sources[rel] = final.decode("utf-8")
        proto_root = Path(repo_root) / manifest["target_root"]
    else:
        origin = str(target_root)
        for rel, (baseline, final) in expected.items():
            state, reason = boot.classify(target_root, rel, baseline, final)
            if state != boot.OK:
                raise ContractError(f"integrity: {rel}: {state} ({reason})")
            sources[rel] = (Path(target_root) / rel).read_text(encoding="utf-8")
        proto_root = Path(target_root)

    proto = proto_root / PurePosixPath(PROTOTYPE)
    if proto.is_symlink() or not proto.is_file():
        raise ContractError(f"integrity: missing tracked prototype {proto}")
    sources[PROTOTYPE] = proto.read_text(encoding="utf-8")
    return sources, origin


# -- contract ----------------------------------------------------------------

def _active_preconditions(pre):
    return [f.name for f in fields(pre) if getattr(pre, f.name)]


def check_contract(sources, preconditions=rt.GM110C_PRECONDITIONS,
                   allow_hypothetical=False, manifest_firmware="GM1.10C",
                   runtime_facts=UNVERIFIED_RUNTIME_FACTS):
    findings = []

    def add(check, ok, detail, label=VERIFIED_SOURCE):
        findings.append(Finding(check, label, bool(ok), detail))

    def guarded(check, fn):
        try:
            fn()
        except (ContractError, KeyError, ValueError) as exc:
            add(check, False, f"cannot evaluate: {exc}")

    cam = sources.get("platform/g3x/platform_camera.h", "")
    kbd_h = sources.get("platform/g3x/platform_kbd.h", "")
    kbd_c = sources.get("platform/g3x/kbd.c", "")
    proto = sources.get(PROTOTYPE, "")

    # C1: the files this contract reads must all be present.
    needed = ["platform/g3x/kbd.c", "platform/g3x/lib.c",
              "platform/g3x/platform_camera.h", "platform/g3x/platform_kbd.h",
              "platform/g3x/shooting.c", PROTOTYPE]
    missing = [rel for rel in needed if rel not in sources]
    add("C1.sources", not missing,
        "all required sources present" if not missing else f"missing: {missing}")

    # C2: configuration the runtime interfaces depend on.
    def c2_platform():
        platform, sub = define(cam, "PLATFORM").strip('"'), define(cam, "PLATFORMSUB").strip('"')
        want = manifest_firmware.replace("GM", "").replace(".", "").lower()
        add("C2.platform", (platform, sub) == ("g3x", want),
            f"PLATFORM={platform!r} PLATFORMSUB={sub!r}, manifest {manifest_firmware}")
        add("C2.dryos", numeric_define(cam, "CAM_DRYOS") == 1, "CAM_DRYOS == 1")

    def c2_keys():
        keys = keymap(kbd_c)
        masks = [numeric_define(kbd_h, f"KEYS_MASK{i}") for i in range(3)]
        options = re.fullmatch(r'\{(.*)\}', define(cam, "CAM_ALT_BUTTON_OPTIONS"))
        if not options:
            raise ContractError("CAM_ALT_BUTTON_OPTIONS is not a brace list")
        alt = [k.strip() for k in options[1].split(",")]
        absent = [k for k in alt if k not in keys]
        add("C2.alt_in_keymap", not absent,
            f"ALT options {alt} in keymap" + (f"; absent {absent}" if absent else ""))
        uncovered = [k for k in alt if k in keys and
                     (keys[k][0] != 0 or keys[k][1] & ~masks[0])]
        add("C2.alt_in_mask0", not uncovered,
            f"KEYS_MASK0=0x{masks[0]:08X} covers every ALT option"
            + (f"; uncovered {uncovered}" if uncovered else ""))
        add("C2.power_excluded", masks[0] & KEY_POWER_BIT == 0,
            "Power (bit 17) not in KEYS_MASK0")
        add("C2.mask12_zero", masks[1] == 0 and masks[2] == 0,
            "KEYS_MASK1/2 are zero (only word 0 is overridden)")

    guarded("C2.platform", c2_platform)
    guarded("C2.keys", c2_keys)

    # C4 first: the C3 limits are derived from the accepted preconditions.
    active = _active_preconditions(preconditions)
    hypothetical = bool(active)
    if hypothetical and not allow_hypothetical:
        add("C4.preconditions", False,
            f"refused: preconditions {active} are not verified for GM1.10C")
    else:
        add("C4.preconditions", True,
            "GM1.10C defaults: no precondition verified" if not active
            else f"HYPOTHETICAL run with {active} (explicitly allowed)",
            HYPOTHETICAL if hypothetical else VERIFIED_SOURCE)
    effective = preconditions if (not hypothetical or allow_hypothetical) \
        else rt.GM110C_PRECONDITIONS

    # The model under these preconditions decides what may be active.
    model = rt.RuntimeLifecycle(effective)
    model.init_core()
    model.install_intercept()
    model.create_spytask()
    for task in rt.REPLACEMENTS:
        model.on_firmware_create_task(task)
    model.file_modules_finished(True)
    allowed = {
        "intercept": model.intercept is rt.InterceptState.INSTALLED,
        "kbd": model.kbd is rt.TaskState.RUNNING,
        "gate": model.gate is rt.GateState.READY,
        "spytask": model.spytask is rt.TaskState.RUNNING,
    }
    model_label = HYPOTHETICAL if hypothetical else VERIFIED_SOURCE
    add("C4.model_trace", not rt.check_trace(model.trace),
        f"PORT-9A trace valid; allows {sorted(k for k, v in allowed.items() if v) or 'nothing'}",
        model_label)
    if not hypothetical:
        add("C4.defaults_inert", not any(allowed.values()),
            "PORT-9A GM1.10C defaults activate no interface")

    # C3: source must not activate an interface the model does not allow.
    def c3():
        everything = "\n".join(sources.values())
        source_active = {
            "intercept": any(mentions(everything, n) for n in ("CreateTask_my", "hook_CreateTask")),
            "kbd": defines_function(everything, rt.REPLACEMENTS["PhySw"]),
            "gate": (defines_function(everything, rt.REPLACEMENTS["InitFileModules"])
                     or mentions(everything, "core_spytask_can_start")),
            "spytask": asm_calls(proto, "CreateTask_spytask"),
        }
        for name, is_active in source_active.items():
            ok = allowed[name] or not is_active
            add(f"C3.{name}", ok,
                f"source {'activates' if is_active else 'does not activate'} {name}; "
                f"model {'allows' if allowed[name] else 'forbids'} it")
        add("C3.stock_physw", asm_calls(proto, "sub_fc1283d2"),
            "prototype task_Startup_my still calls the stock PhySw creator")

    guarded("C3.interfaces", c3)

    # C5: unverified runtime facts stay unverified and address-free.
    flag_names = {f.name for f in fields(rt.Preconditions)}
    for fid, flag, text in runtime_facts:
        if re.search(r"0x[0-9a-fA-F]{4,}|\b[0-9a-fA-F]{8}\b", text):
            add(f"C5.{fid}", False, f"registry entry carries an address: {text}")
            continue
        if flag is not None and flag not in flag_names:
            add(f"C5.{fid}", False, f"unknown precondition flag {flag!r}")
            continue
        claimed = flag is not None and getattr(effective, flag)
        add(f"C5.{fid}", True,
            f"{text}: " + ("assumed (hypothetical)" if claimed else "UNKNOWN"),
            HYPOTHETICAL if claimed else UNVERIFIED_RUNTIME)
    covered = {flag for _, flag, _ in runtime_facts if flag}
    add("C5.coverage", covered == flag_names,
        "every PORT-9A precondition has a registry entry"
        + ("" if covered == flag_names else f"; missing {sorted(flag_names - covered)}"))
    return findings


def violations(findings):
    return [f for f in findings if not f.ok]


def run(target_root=None, manifest_path=boot.DEFAULT_MANIFEST, out=sys.stdout):
    try:
        sources, origin = load_sources(target_root, manifest_path)
    except ContractError as exc:
        print(f"ERROR {exc}", file=out)
        return 3
    findings = check_contract(sources)
    print(f"SOURCES {origin}", file=out)
    for f in findings:
        print(f"{'PASS' if f.ok else 'FAIL':4} {f.label:18} {f.check:22} {f.detail}", file=out)
    bad = violations(findings)
    if bad:
        print(f"RESULT violation: {len(bad)} check(s) failed", file=out)
        return 1
    print("RESULT ok: contract holds; firmware runtime facts remain UNVERIFIED", file=out)
    return 0


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--target", type=Path,
                        help="bootstrapped CHDK tree to read (default: rebuild in memory)")
    parser.add_argument("--manifest", type=Path, default=boot.DEFAULT_MANIFEST)
    args = parser.parse_args(argv)
    return run(args.target, args.manifest)


if __name__ == "__main__":
    sys.exit(main())
