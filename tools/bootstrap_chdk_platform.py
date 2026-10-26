#!/usr/bin/env python3
"""PORT-8A: deterministic offline bootstrap of the GM1.10C platform/g3x sources.

chdk-port/platform/g3x is locally authored, absent from upstream CHDK r5491
and Git-ignored. This tool recreates the minimal source set recorded in
vendor/g3x-platform/MANIFEST.json, applying the listed patches (PORT-7B
patch 0002) to the vendored baselines.

Guarantees:
* Fail-closed: vendored bytes, patch pre/postimages and the patch header
  hashes must all match the manifest before anything is planned.
* Plan before write: if any target file is in an unexpected state (unknown
  hash, symlink, non-regular file) nothing is written.
* Only a missing file is created, or a file that still holds the exact
  recorded baseline is advanced to the final hash. Writes are re-validated at
  execution time (see "Concurrency" below).
* Idempotent: a second run reports every file OK and writes nothing.
* --verify-only never writes.

Concurrency (PORT-8A review of 5a08a92):
* One writing bootstrap per target root: an exclusive non-blocking flock on
  the target root directory; a second writer exits 2. Advisory only.
* Every write is made relative to directory descriptors opened component by
  component with O_NOFOLLOW from the target root, so a symlink swapped into
  the path at any time fails closed instead of redirecting the write.
* CREATE links the new file in with linkat(), which never replaces an entry.
* ADVANCE atomically renames the destination aside, hashes the inode it moved,
  and links the final file in only if that inode is the exact baseline and the
  name is still free; otherwise the moved file is restored (or kept beside the
  destination if the name was taken) and the run stops with a conflict.
* Precondition (not enforceable): no other process writes these files in
  place through an already-open descriptor during a run. Such a write landing
  after the ADVANCE hash check would be lost, and the destination name is
  briefly absent during ADVANCE. Path-level changes (new files, save-by-rename,
  symlink swaps, other bootstrap runs) are not overwritten.

Exit codes: 0 all final (or written), 1 writes pending (verify-only),
2 local conflict, 3 integrity/manifest error.
Standard library only. No subprocess, compiler, ROM or network access.

Usage:
  python3 -B tools/bootstrap_chdk_platform.py [--verify-only] [--target DIR]
"""

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import secrets
import stat
import sys


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "vendor/g3x-platform/MANIFEST.json"

OK, CREATE, ADVANCE, CONFLICT = "OK", "CREATE", "ADVANCE", "CONFLICT"
DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


class IntegrityError(Exception):
    pass


class ConflictError(Exception):
    pass


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def safe_relpath(value):
    path = PurePosixPath(value)
    if (not value or "\\" in value or path.is_absolute()
            or any(part in ("", ".", "..") for part in path.parts)):
        raise IntegrityError(f"Unsafe manifest path: {value!r}")
    return path


def apply_unified_patch(original, patch_text, target):
    """Apply a single-file unified diff exactly; any mismatch raises IntegrityError."""
    lines = patch_text.splitlines()
    try:
        start = lines.index("--- a/" + target)
    except ValueError:
        raise IntegrityError(f"Patch has no --- a/{target} header") from None
    if start + 1 >= len(lines) or lines[start + 1] != "+++ b/" + target:
        raise IntegrityError("Patch +++ header does not match target")
    if any(l.startswith("--- ") for l in lines[start + 2:]):
        raise IntegrityError("Patch touches more than one file")

    src = original.splitlines(keepends=True)
    out, pos, i = [], 0, start + 2
    while i < len(lines):
        m = re.fullmatch(r'@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@.*', lines[i])
        if not m:
            raise IntegrityError(f"Unexpected patch line: {lines[i]!r}")
        old_start, old_len, new_len = int(m[1]), int(m[2] or 1), int(m[4] or 1)
        if old_start - 1 < pos:
            raise IntegrityError("Overlapping or unordered hunks")
        out.extend(src[pos:old_start - 1])
        pos, i, old_seen, new_seen = old_start - 1, i + 1, 0, 0
        while i < len(lines) and not lines[i].startswith("@@"):
            tag, text = lines[i][:1], lines[i][1:]
            if tag in (" ", "-"):
                if pos >= len(src) or src[pos].rstrip("\n") != text:
                    raise IntegrityError(f"Hunk does not match preimage at line {pos + 1}")
                if tag == " ":
                    out.append(src[pos])
                pos, old_seen, new_seen = pos + 1, old_seen + 1, new_seen + (tag == " ")
            elif tag == "+":
                out.append(text + "\n")
                new_seen += 1
            else:
                raise IntegrityError(f"Unsupported hunk line: {lines[i]!r}")
            i += 1
        if (old_seen, new_seen) != (old_len, new_len):
            raise IntegrityError("Hunk line counts disagree with header")
    out.extend(src[pos:])
    return "".join(out)


def load_manifest(path):
    path = Path(path)
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise IntegrityError(f"Cannot read manifest {path}: {exc}") from None
    if manifest.get("schema") != 1 or not manifest.get("files"):
        raise IntegrityError("Unsupported or empty manifest")
    seen = set()
    for entry in manifest["files"]:
        rel = str(safe_relpath(entry.get("path", "")))
        if rel in seen:
            raise IntegrityError(f"Duplicate manifest path {rel}")
        seen.add(rel)
        for key in ("baseline_sha256", "final_sha256"):
            if not re.fullmatch(r"[0-9a-f]{64}", entry.get(key, "")):
                raise IntegrityError(f"{rel}: invalid {key}")
    for patch in manifest.get("patches", []):
        safe_relpath(patch.get("file", ""))
        if str(safe_relpath(patch.get("target", ""))) not in seen:
            raise IntegrityError(f"Patch target not in manifest: {patch.get('target')}")
    safe_relpath(manifest.get("target_root", ""))
    return manifest


def build_expected(manifest, manifest_path, repo_root=REPO_ROOT):
    """Return {relpath: (baseline_bytes, final_bytes)} after full integrity checks."""
    vendor_root = Path(manifest_path).resolve().parent
    contents = {}
    for entry in manifest["files"]:
        rel = entry["path"]
        try:
            data = (vendor_root / rel).read_bytes()
        except OSError as exc:
            raise IntegrityError(f"Missing vendored file {rel}: {exc}") from None
        if sha256(data) != entry["baseline_sha256"] or len(data) != entry.get("size", len(data)):
            raise IntegrityError(f"Vendored {rel} does not match recorded baseline")
        contents[rel] = data

    finals = dict(contents)
    for patch in manifest.get("patches", []):
        rel = patch["target"]
        text = (Path(repo_root) / patch["file"]).read_text(encoding="utf-8")
        for label, key in (("Preimage", "preimage_sha256"), ("Postimage", "postimage_sha256")):
            header = re.findall(r'^# ' + label + r'\s+SHA-256:\s*([0-9a-f]{64})\s*$', text, re.M)
            if header != [patch[key]]:
                raise IntegrityError(f"{patch['file']}: {label} header disagrees with manifest")
        if sha256(finals[rel]) != patch["preimage_sha256"]:
            raise IntegrityError(f"{patch['file']}: unexpected preimage for {rel}")
        post = apply_unified_patch(finals[rel].decode("utf-8"), text, rel).encode("utf-8")
        if sha256(post) != patch["postimage_sha256"]:
            raise IntegrityError(f"{patch['file']}: postimage hash mismatch")
        finals[rel] = post

    for entry in manifest["files"]:
        if sha256(finals[entry["path"]]) != entry["final_sha256"]:
            raise IntegrityError(f"{entry['path']}: final hash disagrees with manifest")
    return {rel: (contents[rel], finals[rel]) for rel in contents}


def classify(target_root, rel, baseline, final):
    dest = Path(target_root)
    for part in PurePosixPath(rel).parts:
        dest = dest / part
        if dest.is_symlink():
            return CONFLICT, f"symlink in path ({dest})"
    if not os.path.lexists(dest):
        return CREATE, "missing"
    if not dest.is_file():
        return CONFLICT, "not a regular file"
    current = sha256(dest.read_bytes())
    if current == sha256(final):
        return OK, "final hash"
    if current == sha256(baseline):
        return ADVANCE, "recorded baseline; patch pending"
    return CONFLICT, f"unexpected local content sha256={current}"


def plan(target_root, expected):
    return [(rel, *classify(target_root, rel, *expected[rel])) for rel in sorted(expected)]


def _scratch_name(suffix):
    return f".bootstrap-{secrets.token_hex(8)}{suffix}"


def _open_parent(root_fd, rel):
    """Return (dir_fd, basename), walking rel's directories with O_NOFOLLOW."""
    parts = PurePosixPath(rel).parts
    fd = os.dup(root_fd)
    try:
        for part in parts[:-1]:
            try:
                os.mkdir(part, 0o755, dir_fd=fd)
            except FileExistsError:
                pass
            try:
                child = os.open(part, DIR_FLAGS, dir_fd=fd)
            except OSError as exc:
                raise ConflictError(f"{rel}: {part!r} is not a real directory ({exc.strerror})") from None
            os.close(fd)
            fd = child
        return fd, parts[-1]
    except BaseException:
        os.close(fd)
        raise


def _read_nofollow(name, dir_fd):
    try:
        fd = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=dir_fd)
    except OSError as exc:
        raise ConflictError(f"{name}: cannot open without following links ({exc.strerror})") from None
    with os.fdopen(fd, "rb") as handle:
        if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
            raise ConflictError(f"{name}: not a regular file")
        return handle.read()


def _write_scratch(dir_fd, data):
    name = _scratch_name(".tmp")
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o644, dir_fd=dir_fd)
    try:
        with os.fdopen(fd, "wb") as handle:
            os.fchmod(handle.fileno(), 0o644)
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        os.unlink(name, dir_fd=dir_fd)
        raise
    return name


def _link_no_clobber(src, dst, dir_fd):
    # linkat() never replaces an existing entry; it raises FileExistsError.
    os.link(src, dst, src_dir_fd=dir_fd, dst_dir_fd=dir_fd, follow_symlinks=False)


def _advance(dir_fd, name, rel, baseline, scratch):
    aside = _scratch_name(".pre")
    try:
        os.rename(name, aside, src_dir_fd=dir_fd, dst_dir_fd=dir_fd)
    except FileNotFoundError:
        raise ConflictError(f"{rel} disappeared before it could be advanced") from None
    try:
        unchanged = sha256(_read_nofollow(aside, dir_fd)) == sha256(baseline)
    except ConflictError:
        unchanged = False
    if not unchanged:
        try:
            _link_no_clobber(aside, name, dir_fd)
        except FileExistsError:
            raise ConflictError(f"{rel} changed during bootstrap; previous content kept "
                                f"beside it as {aside}") from None
        os.unlink(aside, dir_fd=dir_fd)
        raise ConflictError(f"{rel} changed during bootstrap; restored, not overwritten")
    try:
        _link_no_clobber(scratch, name, dir_fd)
    except FileExistsError:
        os.unlink(aside, dir_fd=dir_fd)  # exact baseline bytes, reproducible from vendor/
        raise ConflictError(f"{rel} was recreated during bootstrap; kept, not overwritten") from None
    os.unlink(aside, dir_fd=dir_fd)


def execute(root_fd, expected, steps):
    """Carry out CREATE/ADVANCE steps; every write is re-validated here."""
    for rel, state, _ in steps:
        if state not in (CREATE, ADVANCE):
            continue
        baseline, final = expected[rel]
        dir_fd, name = _open_parent(root_fd, rel)
        try:
            scratch = _write_scratch(dir_fd, final)
            try:
                if state == CREATE:
                    try:
                        _link_no_clobber(scratch, name, dir_fd)
                    except FileExistsError:
                        raise ConflictError(f"{rel} appeared during bootstrap; not overwritten") from None
                else:
                    _advance(dir_fd, name, rel, baseline, scratch)
            finally:
                os.unlink(scratch, dir_fd=dir_fd)
        finally:
            os.close(dir_fd)


def run(target_root=None, manifest_path=DEFAULT_MANIFEST, verify_only=False,
        repo_root=REPO_ROOT, out=sys.stdout):
    try:
        manifest = load_manifest(manifest_path)
        if target_root is None:
            target_root = Path(repo_root) / manifest["target_root"]
        target_root = Path(target_root)
        if not target_root.is_dir() or target_root.is_symlink():
            raise IntegrityError(f"Target root is not a real directory: {target_root}")
        expected = build_expected(manifest, manifest_path, repo_root)
    except (IntegrityError, OSError, UnicodeDecodeError) as exc:
        print(f"ERROR {exc}", file=out)
        return 3

    root_fd = None
    try:
        if not verify_only:
            try:
                root_fd = os.open(target_root, DIR_FLAGS)
            except OSError as exc:
                print(f"ERROR cannot open target root: {exc}", file=out)
                return 3
            try:
                fcntl.flock(root_fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except BlockingIOError:
                print("RESULT conflict: another bootstrap run holds the target root lock; "
                      "nothing written", file=out)
                return 2

        steps = plan(target_root, expected)
        for rel, state, reason in steps:
            print(f"{state:8} {rel} ({reason})", file=out)
        if any(state == CONFLICT for _, state, _ in steps):
            print("RESULT conflict: nothing written", file=out)
            return 2
        pending = [s for s in steps if s[1] != OK]
        if not pending:
            print("RESULT ok: all files at final hash", file=out)
            return 0
        if verify_only:
            print(f"RESULT pending: {len(pending)} file(s) would be written (verify-only)", file=out)
            return 1
        try:
            execute(root_fd, expected, steps)
        except (ConflictError, OSError) as exc:
            print(f"CONFLICT {exc}", file=out)
            print("RESULT conflict: stopped; no modified file was overwritten", file=out)
            return 2
        if any(state != OK for _, state, _ in plan(target_root, expected)):
            print("ERROR post-write verification failed", file=out)
            return 3
        print(f"RESULT ok: wrote {len(pending)} file(s); all files at final hash", file=out)
        return 0
    finally:
        if root_fd is not None:
            os.close(root_fd)  # also releases the flock


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--verify-only", action="store_true", help="report state; never write")
    parser.add_argument("--target", type=Path, help="CHDK tree root (default: chdk-port)")
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)
    return run(args.target, args.manifest, args.verify_only)


if __name__ == "__main__":
    sys.exit(main())
