#!/usr/bin/env python3
"""PORT-9B / PORT-11B: offline integration contract between PORT-8A sources and PORT-9A.

Checks that the bootstrapped GM1.10C platform sources (PORT-8A) and the
tracked boot prototype agree with the runtime lifecycle and safety model
(PORT-9A / PORT-11B):

  C1 integrity  every manifest file is present and at its final SHA-256
                (PORT-8A build_expected / MANIFEST.json), and the tracked
                boot_prototype.c is a regular file at its pinned SHA-256;
  C2 config     configuration the runtime interfaces rely on (DryOS platform,
                ALT button inside KEYS_MASK0, Power excluded);
  C3 interfaces recognized activation markers for runtime interfaces are
                absent in source unless the PORT-9A preconditions allow them
                (source must not run ahead of evidence; regex/source scanning
                only detects known activation markers and cannot prove the
                absence of arbitrary runtime hooks);
  C4 policy     preconditions are the GM1.10C defaults (all unverified), and
                static ROM evidence (PORT-11A) never authorizes runtime
                activation or hardware execution; anything else is refused
                unless explicitly allowed, and is then reported as
                HYPOTHETICAL, never VERIFIED;
  C5 registry   unverified firmware runtime facts and PORT-11A static vs
                runtime boundaries are listed, address-free;
  C6 hook/fs    PORT-11B runtime hook safety contract and 6-stage filesystem
                readiness promotion requirements are consistent and fail-closed.

Labels: VERIFIED_SOURCE = a property of the checked source text;
STATIC_VERIFIED = static ROM instruction/call-chain evidence from PORT-11A;
UNVERIFIED_RUNTIME = a firmware runtime fact this tool cannot establish;
HYPOTHETICAL = a result computed under preconditions that are not evidence.

Without --target the five platform sources are rebuilt in memory from vendor/
and the patches, and the tracked boot_prototype.c is read and hash-verified
from the repository tree (nothing is written). With --target the target tree
is only read and verified against the manifest and pinned prototype digest.
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
PROTOTYPE_SHA256 = "f7884eb2078e93a0098299e2665c1069ecbc65c7759d8993fa31e38fbb232e68"

VERIFIED_SOURCE = "VERIFIED_SOURCE"
STATIC_VERIFIED = "STATIC_VERIFIED"
UNVERIFIED_RUNTIME = "UNVERIFIED_RUNTIME"
HYPOTHETICAL = "HYPOTHETICAL"

KEY_POWER_BIT = 0x00020000

# Firmware runtime facts the integration needs before runtime activation can be
# authorized (PORT-9A map section 5, refined by PORT-11A/11B). Static ROM targets
# for U1/U2/U3 are STATIC_VERIFIED in PORT-11A, but runtime hook safety, SD/FAT
# mount readiness, and SpyTask placement remain UNVERIFIED_RUNTIME (UNKNOWN).
# Address-free by contract.
UNVERIFIED_RUNTIME_FACTS = (
    ("U1", "create_task_prologue_verified",
     "CreateTask prologue and continuation are STATIC_VERIFIED; runtime hook patch context and cache/IRQ safety"),
    ("U2", "init_file_modules_entry_verified",
     "InitFileModules entry is STATIC_VERIFIED; SD/FAT mount readiness and warm-restart storage safety"),
    ("U3", "physw_entry_verified",
     "PhySw creator, entry and CreateTaskStrictly chain are STATIC_VERIFIED; runtime replacement and stack safety"),
    ("U4", None,
     "SpyTask creation point, priority and readiness dependencies on GM1.10C"),
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


def function_bodies(text, name):
    """Return active code bodies `{ ... }` of function `name` by brace matching."""
    cleaned = strip_c_comments(text)
    bodies = []
    for m in re.finditer(r'\b' + re.escape(name) + r'\s*\([^;{)]*\)\s*\{', cleaned):
        start = m.end() - 1
        depth = 0
        in_str = False
        esc = False
        for idx in range(start, len(cleaned)):
            ch = cleaned[idx]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            else:
                if ch == '"':
                    in_str = True
                elif ch == "{":
                    depth += 1
                elif ch == "}":
                    depth -= 1
                    if depth == 0:
                        bodies.append(cleaned[start:idx + 1])
                        break
    return bodies


def strip_function_bodies(text, names):
    """Return `text` with comments stripped and the named function bodies removed."""
    cleaned = strip_c_comments(text)
    for name in names:
        for body in function_bodies(cleaned, name):
            cleaned = cleaned.replace(body, "{ }", 1)
    return cleaned


def asm_strings(text):
    """Extract concatenated string literal contents from active code."""
    return [m.group(1) for m in re.finditer(r'"((?:\\.|[^"\\])*)"', strip_c_comments(text))]


def asm_calls(text, target):
    """True if active inline asm invokes or references `target`.

    Recognizes direct branches (`b`, `bl`, `bx`, `blx` with optional `.w`/`.n`
    width suffixes), multiple `;`- or `\\n`-separated instructions per string,
    optional labels before instructions, and symbol address loads/references
    (`=target` or bare symbol reference in an asm statement).
    Note: regex/source scanning only detects recognized activation markers;
    it cannot prove the absence of arbitrary runtime hooks.
    """
    esc = re.escape(target)
    branch_pat = (
        r'^\s*(?:[A-Za-z_.$][A-Za-z0-9_.$]*\s*:\s*)*'
        r'b(?:lx|l|x)?(?:\.[nw])?\s+' + esc + r'\b'
    )
    ref_pat = r'(?:=\s*' + esc + r'\b|\b' + esc + r'\b)'
    for lit in asm_strings(text):
        expanded = lit.replace(r"\n", "\n").replace(r"\t", "\t")
        for stmt in re.split(r'[;\n]', expanded):
            stmt_clean = re.sub(r'/\*.*?\*/|//.*|@.*', '', stmt).strip()
            if not stmt_clean:
                continue
            if re.match(branch_pat, stmt_clean, flags=re.I) or re.search(ref_pat, stmt_clean):
                return True
    return False


def has_spytask_activation_marker(sources):
    """True if any source file contains a recognized SpyTask activation marker.

    Checks both the prototype and all other platform sources, ignoring only the
    dormant `spytask` and `CreateTask_spytask` helper definitions in the
    prototype itself. Detects inline asm branches/references to
    `CreateTask_spytask`, `spytask`, `core_spytask`, or `_CreateTask`, as well
    as active C calls/references to those symbols or `"SpyTask"` outside the
    dormant prototype wrapper functions.
    """
    for rel, text in sources.items():
        if asm_calls(text, "CreateTask_spytask") or asm_calls(text, "spytask") or asm_calls(text, "core_spytask"):
            return True
        if rel == PROTOTYPE:
            outside = strip_function_bodies(text, ("spytask", "CreateTask_spytask"))
            # Remove forward declarations of spytask and CreateTask_spytask
            outside_no_decl = re.sub(
                r'\bvoid\s+(?:CreateTask_spytask|spytask)\s*\([^;]*\)\s*;',
                '',
                outside,
            )
        else:
            outside_no_decl = strip_c_comments(text)
        for marker in ("CreateTask_spytask", "core_spytask", "spytask", "_CreateTask", "CreateTask"):
            if re.search(r'\b' + re.escape(marker) + r'\b', outside_no_decl):
                return True
        if re.search(r'"\s*SpyTask\s*"', outside_no_decl):
            return True
    return False


# -- source loading ----------------------------------------------------------

def load_sources(target_root=None, manifest_path=boot.DEFAULT_MANIFEST,
                 repo_root=REPO_ROOT):
    """Return ({relpath: text}, origin). Never writes.

    The vendored baseline and patches are always integrity-checked through
    PORT-8A. Without target_root, the five platform files are rebuilt in memory
    from vendor/ + patches and the tracked boot_prototype.c is read from the
    repository tree. With target_root, every manifest file and boot_prototype.c
    are read from target_root. In both modes, boot_prototype.c must be a
    regular non-symlink file matching PROTOTYPE_SHA256.
    """
    try:
        manifest = boot.load_manifest(manifest_path)
        expected = boot.build_expected(manifest, manifest_path, repo_root)
    except (boot.IntegrityError, OSError, UnicodeDecodeError) as exc:
        raise ContractError(f"integrity: {exc}") from None

    sources = {}
    if target_root is None:
        origin = "in-memory (vendor + patches) + tracked boot_prototype.c"
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

    proto = proto_root
    for part in PurePosixPath(PROTOTYPE).parts:
        proto = proto / part
        if proto.is_symlink():
            raise ContractError(f"integrity: symlink in prototype path {proto}")
    if not proto.is_file():
        raise ContractError(f"integrity: missing tracked prototype {proto}")
    try:
        proto_bytes = proto.read_bytes()
        proto_text = proto_bytes.decode("utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        raise ContractError(f"integrity: cannot read prototype {proto}: {exc}") from None
    actual_sha = boot.sha256(proto_bytes)
    if actual_sha != PROTOTYPE_SHA256:
        raise ContractError(
            f"integrity: {PROTOTYPE}: sha256 mismatch "
            f"(expected {PROTOTYPE_SHA256}, got {actual_sha})"
        )
    sources[PROTOTYPE] = proto_text
    return sources, origin


# -- contract ----------------------------------------------------------------

def _active_preconditions(pre):
    return [f.name for f in fields(pre) if getattr(pre, f.name)]


def check_contract(sources, preconditions=rt.GM110C_PRECONDITIONS,
                   allow_hypothetical=False, manifest_firmware="GM1.10C",
                   runtime_facts=UNVERIFIED_RUNTIME_FACTS,
                   static_evidence=rt.GM110C_STATIC_EVIDENCE,
                   hook_contract=rt.GM110C_HOOK_CONTRACT):
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

    # C1: the files this contract reads must all be present, and the tracked
    # boot prototype must match its pinned SHA-256 digest.
    needed = ["platform/g3x/kbd.c", "platform/g3x/lib.c",
              "platform/g3x/platform_camera.h", "platform/g3x/platform_kbd.h",
              "platform/g3x/shooting.c", PROTOTYPE]
    missing = [rel for rel in needed if rel not in sources]
    add("C1.sources", not missing,
        "all required sources present" if not missing else f"missing: {missing}")
    proto_sha = boot.sha256(proto.encode("utf-8")) if PROTOTYPE in sources else "missing"
    add("C1.prototype_sha256", proto_sha == PROTOTYPE_SHA256,
        f"{PROTOTYPE} matches pinned sha256={PROTOTYPE_SHA256}"
        if proto_sha == PROTOTYPE_SHA256
        else f"{PROTOTYPE} sha256 mismatch: expected {PROTOTYPE_SHA256}, got {proto_sha}")

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

    # C4 first: the C3 limits are derived from the effective preconditions.
    requested_active = _active_preconditions(preconditions)
    requested_hypothetical = bool(requested_active)
    if requested_hypothetical and not allow_hypothetical:
        add("C4.preconditions", False,
            f"refused: preconditions {requested_active} are not verified for GM1.10C")
    else:
        add("C4.preconditions", True,
            "GM1.10C defaults: no precondition verified" if not requested_active
            else f"HYPOTHETICAL run with {requested_active} (explicitly allowed)",
            HYPOTHETICAL if requested_hypothetical else VERIFIED_SOURCE)
    effective = preconditions if (not requested_hypothetical or allow_hypothetical) \
        else rt.GM110C_PRECONDITIONS
    effective_hypothetical = bool(_active_preconditions(effective))

    # Static evidence vs runtime authorization check (PORT-11B Phase 2):
    # Static evidence (U1/U2-entry/U3 STATIC_VERIFIED) must NEVER imply runtime activation.
    static_never_authorizes = (
        not static_evidence.authorizes_runtime_activation
        and rt.GM110C_PRECONDITIONS == rt.Preconditions(False, False, False)
    )
    add("C4.static_vs_runtime_auth", static_never_authorizes,
        "STATIC_VERIFIED ROM evidence never authorizes runtime activation; GM110C_PRECONDITIONS remains all False",
        STATIC_VERIFIED if static_evidence.static_targets_verified else VERIFIED_SOURCE)

    # The model under effective preconditions decides what may be active.
    model = rt.RuntimeLifecycle(effective, static_evidence=static_evidence)
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
    model_label = HYPOTHETICAL if effective_hypothetical else VERIFIED_SOURCE
    add("C4.model_trace", not rt.check_trace(model.trace),
        f"PORT-9A trace valid; allows {sorted(k for k, v in allowed.items() if v) or 'nothing'}",
        model_label)
    if not effective_hypothetical:
        add("C4.defaults_inert", not any(allowed.values()),
            "PORT-9A GM1.10C defaults activate no interface")

    # C3: recognized activation markers in source must be absent unless the
    # model allows the interface. Note: regex/source scanning only detects
    # known activation markers; it cannot prove the absence of arbitrary hooks.
    def c3():
        everything = "\n".join(sources.values())
        source_active = {
            "intercept": any(mentions(everything, n) for n in ("CreateTask_my", "hook_CreateTask")),
            "kbd": defines_function(everything, rt.REPLACEMENTS["PhySw"]),
            "gate": (defines_function(everything, rt.REPLACEMENTS["InitFileModules"])
                     or mentions(everything, "core_spytask_can_start")),
            "spytask": has_spytask_activation_marker(sources),
        }
        for name, is_active in source_active.items():
            ok = allowed[name] or not is_active
            marker_status = (
                "recognized activation marker present"
                if is_active else "recognized activation markers absent"
            )
            add(f"C3.{name}", ok,
                f"{name}: {marker_status} (regex scan only; not a proof against arbitrary hooks); "
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

    # C6: PORT-11B hook safety contract and 6-stage filesystem promotion requirements.
    hook_ok = (
        hook_contract.static_prerequisites_satisfied
        and not hook_contract.runtime_prerequisites_satisfied
        and not hook_contract.all_satisfied
    )
    add("C6.hook_safety_contract", hook_ok,
        "CreateTask static hook prerequisites STATIC_VERIFIED; runtime patch/IRQ/cache/continuation prerequisites remain UNKNOWN",
        UNVERIFIED_RUNTIME if hook_ok else VERIFIED_SOURCE)
    expected_fs_stages = (
        "task_created",
        "task_started",
        "init_returned_normally",
        "mount_observed",
        "fs_io_ready",
        "warm_restart_safe",
    )
    actual_fs_stages = tuple(stage for stage, _ in rt.FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS)
    fs_req_ok = (
        actual_fs_stages == expected_fs_stages
        and all(bool(desc.strip()) for _, desc in rt.FILESYSTEM_PROMOTION_EVIDENCE_REQUIREMENTS)
        and static_evidence.u2_sd_fat_mount_readiness is rt.EvidenceStatus.UNKNOWN
        and static_evidence.u4_spytask_creation_priority_and_dependencies is rt.EvidenceStatus.UNKNOWN
    )
    add("C6.fs_readiness_contract", fs_req_ok,
        "6-stage filesystem readiness contract defined; U2 mount readiness and U4 SpyTask gate remain UNKNOWN",
        UNVERIFIED_RUNTIME if fs_req_ok else VERIFIED_SOURCE)
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
                        help="bootstrapped CHDK tree to read (default: vendor + patches in memory, tracked boot_prototype.c)")
    parser.add_argument("--manifest", type=Path, default=boot.DEFAULT_MANIFEST)
    args = parser.parse_args(argv)
    return run(args.target, args.manifest)


if __name__ == "__main__":
    sys.exit(main())
