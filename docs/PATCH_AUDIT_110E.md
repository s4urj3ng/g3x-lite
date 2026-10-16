# Historical `g3x_110e.patch` audit

Updated: 2026-10-16
Phase: 0B - public-source, read-only archaeology
Status: **BLOCKED - attachment identified but file content is not publicly retrievable as a guest**

## Scope and result

This audit concerns only the text attachment named `g3x_110e.patch`. No firmware archive, executable, installer, camera, build system, or downloaded script was accessed or executed.

The original attachment was located and its provenance established, but the patch bytes could not be recovered through public guest access. Consequently:

- no SHA-256 can be reported;
- the exact byte size cannot be independently measured;
- the complete file list, diff headers, TODOs, addresses, and code cannot be audited;
- no exact CHDK base revision can be established; and
- no patch dry-run can be performed.

It would be unsafe to invent any of those results from the forum summary or from a nearby CHDK snapshot.

## Provenance

### Primary post

- Forum discussion: <https://chdk.setepontos.com/d/12600-g3-x-100c-fw-dump/21>
- Legacy canonical discussion URL: <https://chdk.setepontos.com/index.php?topic=12600.20>
- Post author: `ranma` (forum user 31560)
- Post ID: `143437`; post number 21
- Post timestamp from the forum JSON payload: `2020-05-11T22:43:51Z`
- Retrieval date: 2026-10-16
- Attachment name shown by the forum: `g3x_110e.patch`
- Displayed size: `328.82KB` in the migrated forum and `328.82 kB` in the archived legacy page. This is presentation metadata, **not** a measured byte count.
- Migrated attachment UUID: `51fc3fb9-0f60-456b-ae9c-d090c1a1c176`
- Original legacy attachment URL recovered from the archived primary page: <https://chdk.setepontos.com/index.php?action=dlattach;topic=12600.0;attach=16495>
- Legacy attachment ID: `16495`

The post separately listed `g3x_110e_fw.zip` as attachment 16496. That firmware archive was neither requested nor downloaded.

### Archive evidence

Wayback snapshot used to recover the original attachment URL:

<https://web.archive.org/web/20210729223203id_/https://chdk.setepontos.com/index.php?topic=12600.20>

The snapshot preserves the post and link metadata, including the patch filename, legacy attachment ID, displayed size, and a historical download count of 27. It does not preserve attachment 16495 itself: a direct archived attachment request returned 404, and the CDX index returned no capture for the exact attachment URL.

### Current access blocker

The migrated forum renders the attachment but reports `fof-upload.canDownload: false` for a guest session. Its public download API returned HTTP 403. The original legacy link is now behind a Cloudflare verification page rather than serving the file. No challenge was bypassed and no account was created.

## What the primary author actually claims

The post says the patch is the source corresponding to a proof-of-concept for firmware 1.10E and that only approximately the minimum task hooks were implemented:

| Hook named by author | Author's stated purpose | Verification status |
|---|---|---|
| `task_PhySw` | Keyboard | Verified as a claim in the primary post; implementation unavailable |
| `task_InitFileModules` | Signal that CHDK can start | Verified as a claim in the primary post; implementation unavailable |
| `task_FileWrite` | PTP remote file write | Verified as a claim in the primary post; implementation unavailable |
| `task_TricInitTask` | FI2 boot workaround | Verified as a claim in the primary post; implementation unavailable |

Earlier in the same thread, the author reported playback-mode boot and initial CHDK messages with only `InitFileModules` implemented. Immediately before publishing the patch, the author reported unresolved live-view crashes, particularly in 1080p over HDMI. These statements directly contradict treating the attachment as a complete or stable port.

## Partial structural audit

Only structure exposed in the primary discussion can be verified without the patch bytes:

- A follow-up post shows a generated path `platform/g3x/sub/110e/stubs_entry.S`, proving that at least this G3 X platform/subrevision path existed in the author's working tree.
- The follow-up excerpt labels the generated target `GM1.10E`, DryOS release 57, and main firmware start `0xfc020000`. These are author-generated findings, not independently reproduced facts.
- The four task hooks above indicate work in platform boot/task-hook code and file/keyboard integration, but the exact filenames and implementations remain unknown.
- The forum author later produced a 1.20A binary by changing an auto-generated firmware version check and reported main-stub equivalence. That does not prove the whole 1.10E patch is source-compatible with 1.20A.

### Functionality not established

The patch has not been shown to implement capture hooks, exposure overrides, raw capture, movie control, stable live view, complete keyboard mapping, filesystem safety, UI integration, power management, or the requested G3X Lite features. Absence cannot be proven without the file, but the author's “minimum” description and instability report mean none should be assumed.

### Addresses and TODOs

No address should be attributed to the patch until its text is recovered. Addresses printed elsewhere in the thread are external discussion evidence, not verified patch contents. Likewise, exact TODO markers and commented-out stubs are unknown.

## CHDK base-revision analysis

The exact base revision is **unknown** because the patch headers and context are unavailable.

The authoritative CHDK mirror history provides only a chronological bracket around publication:

| Boundary | SVN revision | Git mirror commit | Timestamp | Meaning |
|---|---:|---|---|---|
| Last trunk commit before forum publication | r5491 | `21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6` | 2020-05-11T01:48:30Z | Latest public trunk state available about 21 hours before the post |
| First trunk commit after forum publication | r5492 | `8cded093bccce82ffe34d904da640fc55e087314` | 2020-05-15T21:31:11Z | Next public trunk change, about four days later |

Mirror: <https://github.com/01luna/CHDK> (history inspected 2026-10-16). Both commits retain `git-svn-id` lines identifying the corresponding Assembla trunk revisions.

This timing proves only that r5491 was the newest public trunk revision at posting time. It does **not** prove the author's checkout used r5491, or even a narrowly recent revision. The narrowest evidence-supported statement is therefore:

> The patch was published between trunk r5491 and r5492. Its required base revision is unknown and may predate r5491.

An exact revision or compatibility range must wait for patch recovery and comparison of its preimage context against repository history.

## Dry-run applicability

Not performed. A dry-run requires both the actual patch and a justified source baseline. Neither prerequisite is available. Applying a reconstructed or inferred diff would not test the historical artifact.

When the patch is lawfully recovered, the reproducible procedure is:

1. Preserve the received bytes unchanged and calculate SHA-256 and exact byte count.
2. Inspect the patch as text only; reject or quarantine it if its content type or magic is not text.
3. Extract diff paths, timestamps, revision markers, and index lines.
4. Search CHDK history for every preimage hunk; intersect matching revision ranges rather than selecting by date alone.
5. Check out the uniquely supported revision into a temporary directory.
6. Run `git apply --check --verbose /absolute/path/to/g3x_110e.patch` only. Do not apply, build, or execute.
7. Record the source commit, mapped SVN revision, command, exit status, rejected hunks, and any ambiguity.

## Evidence classification

### Verified

- The named text patch was attached by `ranma` to post 143437 on 2020-05-11T22:43:51Z.
- Its legacy attachment ID is 16495 and its migrated UUID is recorded above.
- The forum displays a nominal size of 328.82 kB/KB.
- The author described four minimal hooks and did not claim a complete port.
- Public trunk r5491 preceded publication and r5492 followed it.
- Guest retrieval currently fails, and the archive lacks the patch payload.

### Plausible but unverified

- The patch was probably produced against a trunk checkout near its publication date.
- It probably creates a broader `platform/g3x` tree modeled on another DIGIC 6 port.

These statements are not sufficient for a base-revision choice or implementation claim.

### Unknown

- Exact bytes, SHA-256, measured size, encoding, line endings, and license notices.
- Exact base revision and whether the diff was made from a clean checkout.
- Complete file list, hook implementations, addresses, TODOs, build status, and applicability.
- Whether an authenticated forum user can still retrieve the attachment successfully.

## Blocker resolution

A human may resolve the blocker by obtaining the text attachment through an authorized CHDK forum account or directly from the original author, then placing only that `.patch` file in a reviewed local location. Do not provide or download either firmware ZIP. The next agent must verify the file type, exact size, and SHA-256 before reading it and must not execute any content.
