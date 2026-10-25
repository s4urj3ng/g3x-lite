# PORT-5A — Ranma G3 X CHDK port archaeology

Date: **2026-10-25 (Asia/Seoul)**. Analyst: Claude Code. Workspace: `/Users/avp/project/g3x-lite`, branch `docs/port4-documentation-consolidation`, HEAD `57968eb` (dirty/untracked work preserved).
Scope: public source retrieval and historical documentation review only. No firmware disassembly, builds, code execution, hardware or SD operations. No executable project file was modified.

**Result: NOT_FOUND (patch source).** The thread, its posts and its attachment metadata were recovered and re-authenticated. The bytes of `g3x_110e.patch` were **not**:
- The forum denies guest downloads (HTTP 403 `permission_denied`).
- No public archive or mirror holds a copy.

Retrieval stopped at that access control. No login, account creation, challenge bypass or third-party re-host was attempted. No historical-reference directory was created, because no authentic source was obtained.

This report supersedes nothing in [PATCH_AUDIT_110E.md](PATCH_AUDIT_110E.md) (2026-10-16, BLK-03). It re-verifies that audit on a new date, widens the mirror search and adds the comparison with PORT-3/PORT-4.

## 1. Classification

- **VERIFIED (source):** read from the cited primary source on 2026-10-25.
- **VERIFIED (doc):** recorded in an existing project document; not re-derived.
- **AUTHOR CLAIM:** what ranma states, with no artifact available to check it against.
- **UNKNOWN:** not established.

## 2. Provenance (retrieved 2026-10-25)

| Item | Evidence | Status |
|---|---|---|
| Thread | `https://chdk.setepontos.com/d/12600-g3-x-100c-fw-dump?page=2`. Public API `https://chdk.setepontos.com/api/discussions/12600` returned title "G3 X 1.00C FW Dump", created 2015-09-15T07:38:39Z, 25 posts. | VERIFIED (source) |
| Post list | `https://chdk.setepontos.com/api/posts?filter[discussion]=12600` returned all 25 posts. The HTML page renders through JavaScript only, so WebFetch saw no posts; the JSON API is the same public data. | VERIFIED (source) |
| ranma's complete posting history | `https://chdk.setepontos.com/api/posts?filter[author]=ranma` returned **7 posts, all in thread 12600** (143399, 143401, 143433, 143436, 143437, 143438, 143439; 2020-05-04 → 2020-05-12). No other thread carries a copy or a later version. | VERIFIED (source) |
| Patch post | Post **143437**, number 21, 2020-05-11T22:43:51Z, not edited. Attachments: `g3x_110e.patch` (328.82KB, fof-upload UUID `51fc3fb9-0f60-456b-ae9c-d090c1a1c176`) and `g3x_110e_fw.zip` (174.64KB, UUID `dc9012be-4203-43fc-9fe8-9c35d419401f`). | VERIFIED (source) |
| 1.20A post | Post **143439**, 2020-05-12T18:09:55Z. Attachment `g3x_120a_fw.zip` (174.83KB, UUID `5f78d11e-0dfb-421b-9edc-c7d26673311c`). | VERIFIED (source) |
| Legacy (SMF) attachment IDs | Wayback capture `https://web.archive.org/web/20210729223203id_/https://chdk.setepontos.com/index.php?topic=12600.20` links `attach=16495` (`g3x_110e.patch`, "328.82 kB - downloaded 27 times"), `16496` (`g3x_110e_fw.zip`, 26 downloads) and `16497` (`g3x_120a_fw.zip`, 25 downloads). | VERIFIED (source); matches PATCH_AUDIT_110E |

Sizes are forum display metadata, not measured byte counts.

## 3. Retrieval attempts (all 2026-10-25)

| Route | Result | Status |
|---|---|---|
| Forum download through the normal guest flow (`/api/fof/download/<uuid>/143437/<session csrf>`) | HTTP **403** `{"errors":[{"status":"403","code":"permission_denied"}]}` | **BLOCKED by access control. Stopped, not bypassed.** |
| Wayback availability API, legacy URLs `attach=16495/16496/16497` (both `;` and `&` forms) | `archived_snapshots: {}` for all six | Not archived |
| Wayback CDX, exact legacy URL with sorted parameters | No captures | Not archived |
| CHDK trunk mirror `https://github.com/01luna/CHDK`, `master` @ `92208bf004e193c30b625065889bd533732a524b` (pushed 2025-11-17) | `platform/` contains `g5x`, `g7x`, `g7x2`, `m10`, `sx710hs` etc., **no `g3x`**. Commit search for "g3x" finds only finsig_thumb2 signature work (r4437, r4438, r4444; Feb 2016), and no port. | Not upstream |
| Assembla SVN `subversion.assembla.com/svn/chdk/trunk/platform/` | HTTP 401 (auth required); `app.assembla.com` 403 | Not accessible; not pursued |
| GitHub user `ranma` (all public repos listed via API) | No CHDK, Canon or G3 X repository | Not found |
| GitHub repository search "chdk g3x"; code search "GM1.10E" | No external hits; the only code hits are this project's own docs | Not found |
| Web search (`"g3x_110e.patch"`, ranma CHDK G3 X) | Only Canon firmware notices and general CHDK pages | Not found |

The binary ZIPs were not requested from any source (task rule: no historical experimental binaries).

## 4. Recovered file inventory

| File | Recovered | Location |
|---|---|---|
| `g3x_110e.patch` | **No** | n/a |
| `g3x_110e_fw.zip` | Not attempted (binary) | n/a |
| `g3x_120a_fw.zip` | Not attempted (binary) | n/a |
| Thread post text and metadata (25 posts) | Yes, as public JSON in the session scratchpad only; summarized here | Not committed (forum content, not source) |

**Patch fragments visible in public posts.** These are the only verbatim source-tree fragments available:
- Post 143438 contains a diff header `--- platform/g3x/sub/110e/stubs_entry.S 2020-05-12 09:52:34` / `+++ platform/g3x/sub/120a/stubs_entry.S 2020-05-12 19:57:29`, with comment lines:
  - `Main firmware start: 0xfc020000`
  - `DRYOS R57 ... @ 0xfc616ec8 ref @ 0xfc0359c8`
  - `"GM1.10E" @ 0xfc54e0b5`
  - `PLATFORMOSVER = 57`
- This proves that `platform/g3x/sub/110e/` and `platform/g3x/sub/120a/` existed in ranma's tree.
- It is a generated stub file, not the patch itself.

## 5. Upstream base revision

**Not proven.** No patch headers or preimage context are available.

The chronological bracket from PATCH_AUDIT_110E still holds. The newest public trunk revision at posting time was r5491 (`21b9a14e…`, 2020-05-11T01:48:30Z), and the next was r5492 (2020-05-15). That proves only "published between r5491 and r5492". The base may be older.

Our own candidate is also built on **r5491** (`candidate_port2a/candidate_manifest.json`). That is a choice made in this project, and it is not evidence of ranma's base.

## 6. Firmware-variant differences

| Pair | Evidence | Status |
|---|---|---|
| GM1.10E vs GM1.20A | ranma (post 143438): main firmware stub addresses are "basically identical". The PRIMARY dump diff shown changes only version strings and the build date (`Nov 27 2017 21:48:04` → `Nov 27 2019 13:52:02`), plus a root certificate at `0x01f00000` (AddTrust → COMODO). The 1.20A binary differed from 1.10E only in "the auto-generated firmware version check" (post 143439). | AUTHOR CLAIM; diff is excerpted (`[...]`), so it is not a full-image comparison |
| GM1.10E vs GM1.10C (our target) | No public source compares them. Both are public 1.1.0.0, but they are distinct internal builds (C011, owner screen E037). | **UNKNOWN**. No 1.10E address may be assumed valid on 1.10C. |
| GM1.10E/1.20A vs 1.00C | 1.00C is the dump this thread started with (Nippey, 2015). No variant comparison was published. | UNKNOWN |

Stub-address equivalence between E and A does **not** imply equivalence between E and C. The 10E/20A string at `0xfc54e0b5` has already been seen to differ in our own GM1.10C work (HDMI001 / E034 records it as a historical lead only).

## 7. Source components named in the record

The implementations are inaccessible. Only ranma's descriptions exist, all AUTHOR CLAIM:

| Component | What ranma states | Source post |
|---|---|---|
| Early boot / loader | Boots as `DISKBOOT.BIN` and as `PS.FI2`. The FI2 path needed a workaround (see TricInitTask). Boots **in Playback only**, showing initial CHDK messages. | 143399, 143436, 143437 |
| RAM / ARAM placement | Instability ("live view crashing, in particular 1080p over HDMI, … within a minute") was attributed to memory use or timing. ranma "set 'ARAM' to a different area and enabled CHDK from ARAM": an "apparently unused" region `0x00c16b90–0x00dfffff`, guessed to belong to an Xtensa core (`Dry[Zico]` near `0xc00000`, `EPC`/`EXCVADDR` near `0xe00000`). Evidence was a RAM fill with `0xdeadbeef` and a later PTP dump. ranma said it "_seems_" to help, "needs more testing", and that the Xtensa heap boundaries should be double-checked. | 143433, 143436 |
| DryOS task hooks | "Only the ~minimum of task hooks". Initially none except InitFileModules (143399). | 143399, 143437 |
| `task_InitFileModules` | "Signal that CHDK can start". | 143437 |
| `task_FileWrite` | "PTP remote file write". | 143437 |
| `task_PhySw` | "Keyboard". | 143437 |
| `task_TricInitTask` | "FI2 boot workaround". | 143437 |
| MPU / RAM mirror | 512 MB RAM mirrored at `0x20000000`/`0x60000000` (srsa_4c). ranma: ATCM exception vectors are not mirrored, so the first 4 KiB of the mirror can be written "without consequences AFAICS". Suggested an unused MPU region as a guard. | 143435, 143436 |

The hook mechanism is unknown: which wrapper, which addresses, and whether it is CHDK's standard `taskcreate`/`taskNameHook` pattern. So are spytask placement and the capture, movie, GUI and draw hooks. Nothing beyond the four hooks should be assumed present.

## 8. Comparison with PORT-3/PORT-4 findings

| Topic | ranma (GM1.10E, 2020) | This project (GM1.10C) | Assessment |
|---|---|---|---|
| Boot architecture | Standard CHDK DISKBOOT/FI2 boot (implied by "DISKBOOT.BIN and PS.FI2" and CHDK task hooks), i.e. close to our **Architecture A** (restart/startup hooking) | A is a **blocked reference** with hardware NO-GO ([PORT-4B](PORT4B_BOOT_ARCHITECTURE_DECISION.md), [PORT-3C](PORT3C_RESTART_READINESS_MATRIX.md): `NOT_PROVEN_SAFE`). B unproven; C residency UNKNOWN ([PORT-4C](PORT4C_MEMORY_OWNERSHIP_LIFETIME.md)). | ranma's report is evidence that an A-style boot *reached Playback with messages* on **1.10E**. It is not evidence about our IRQ/SD restart blockers, which remain open, and not evidence for 1.10C. |
| Stability | Live-view crashes; Playback-only boot; experimental | No hardware boot of a CHDK core attempted | A historical Playback boot is not a stable port (task rule). It matches PATCH_AUDIT_110E / C001. |
| Core placement | Initially unknown placement; later "CHDK from ARAM" at `0x00c16b90–0x00dfffff` | Candidate puts the core at `MEMISOSTART=0x3489b4` and shifts the DryOS heap base to `0x00366C90` (upper `0x00600014`). ARAM heap documented as `0x006CE000..0x006F0000` (`0x22000`), from ROM `0xFC05B454`/`0xFC55888C`. Candidate sets `OPT_ARAM_MALLOC=1`, `OPT_CHDK_IN_ARAM` empty. | **Different regions and different meanings of "ARAM".** ranma's region is a hand-picked "apparently unused" range that ranma redefined as ARAM; ours is the firmware's ARAM heap. Neither is proven free on 1.10C. ranma's Xtensa-ownership guess is unverified, and the pool-upper-bound contradiction (`0x0060E000` vs `0x00600014`) in PORT-4C remains. |
| Task hooks | PhySw, InitFileModules, FileWrite, TricInitTask | Candidate: spytask, GUI and keyboard hooks all **inactive**. Stock `task_PhySw` launched unmodified. No hook implemented. | ranma's list is a useful **minimum-hook inventory** to compare against later, but the code is absent. Our task-creation/injection work is outside the current scope (PORT-4D boundary). |
| FI2 path | Required a TricInitTask workaround | Our work uses DISKBOOT/Canon Basic only | Suggests FI2 boot on G3 X has a task-ordering quirk (AUTHOR CLAIM). Not applicable to current scope. |
| Firmware variants | E and A treated as interchangeable | Target is 1.10C, distinct from E (C011) | No 1.10E or 1.20A address carries over without independent 1.10C verification. |

## 9. Remaining evidence gaps

1. The patch bytes themselves: SHA-256, exact size, file list, base revision, hook implementations, memory configuration (`makefile.inc` values), and how ranma's FI2 workaround works.
2. Whether a logged-in forum account can download attachment 16495 or UUID `51fc3fb9…`. Untested by design.
3. Any GM1.10E ↔ GM1.10C comparison.
4. Whether ranma's `0x00c16b90–0x00dfffff` region exists or is free on 1.10C. Unverified even on 1.10E by ranma's own statement.
5. Whether the 1.10E port ever became stable after 2020-05-12. The thread has no further ranma posts. A 2023 user (posts 149969/149971) could not boot.

## 10. Recommended next step

An owner decision is needed. The only legitimate recovery routes left are human ones:

1. The owner downloads `g3x_110e.patch` with their own CHDK forum account, if they have or choose to create one, and only the `.patch`, never the ZIPs.
2. Or the owner asks ranma directly (forum PM to user 31560) for the patch and its CHDK base revision.

If the file is supplied, place it unmodified under a historical-reference directory, for example `historical/ranma_g3x_110e/` (text only, not built or applied). Then run the verification procedure in [PATCH_AUDIT_110E § Dry-run applicability](PATCH_AUDIT_110E.md): SHA-256, text-type check, header extraction, and preimage matching against `01luna/CHDK` history, with a `git apply --check` only.

Until then, BLK-03 stays open. ranma's thread is usable only as **author-claim context**, not as source or as a safety precedent.

## 11. Boundary record

- **Done:**
  - Public forum JSON reads: discussion, posts, author filter.
  - One guest download attempt, which returned 403, after which that route was stopped.
  - Wayback availability/CDX queries.
  - GitHub API reads of `01luna/CHDK` and `ranma`.
  - Web search.
  - Read-only greps of our own docs, the candidate manifest and makefiles.
- **Not done:** login or account use, bypass of 403/401/Cloudflare, ZIP downloads, firmware disassembly, builds, execution, hardware or SD operations, modification of executable files, commits, pushes or PRs.

Exact next command:

```sh
cat /Users/avp/project/g3x-lite/docs/PORT5A_RANMA_PORT_RECOVERY.md
```
