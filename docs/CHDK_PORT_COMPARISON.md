# CHDK source archaeology: G3 X reference ports

Updated: 2026-10-16  
Scope: Phase 0C, source and forum text only. No firmware, build, payload, or camera use.

## Question and evidence boundary

This note asks one bounded question: what can the historical G5 X, M10, G16, and SX710 HS sources at CHDK trunk r5491-r5492 establish about the source dependencies of a hypothetical G3 X port?

The comparison snapshot is CHDK SVN r5491, mirrored as Git commit [`21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6`](https://github.com/01luna/CHDK/commit/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6), dated 2020-05-11T01:48:30Z. r5492 is [`8cded093bccce82ffe34d904da640fc55e087314`](https://github.com/01luna/CHDK/commit/8cded093bccce82ffe34d904da640fc55e087314), dated 2020-05-15T21:31:11Z. A tree comparison shows that only `modules/gui_fselect.c` changed between them; the four platform directory tree objects are identical. This makes either revision equivalent for the reference-port files discussed here. It does **not** identify the missing G3 X patch's base revision.

All URLs were retrieved or rechecked on 2026-10-16.

## Why these four ports

The selection is primary historical evidence, not a similarity inference:

- In [forum post 143401](https://chdk.setepontos.com/d/12600-g3-x-100c-fw-dump/16), 2020-05-04T20:25:29Z, ranma said the G5 X port was the starting reference and that M10 and G16 were also helpful.
- In [post 143400](https://chdk.setepontos.com/d/12600-g3-x-100c-fw-dump/15), 2020-05-04T19:59:42Z, reyalp identified SX710 and M10 as other DryOS R57 ports.
- In [post 143418](https://chdk.setepontos.com/d/12600-g3-x-100c-fw-dump/17), 2020-05-08T14:55:22Z, waterwingz said the G16 port had been made with CHDK's `capdis` tool.

These statements prove which sources informed the attempt. They do not prove binary compatibility or that code was copied unchanged.

## Revision and platform matrix

| Port | First mirrored trunk addition | r5491 firmware subdirectories | Source-declared generation / OS | Boot and memory declarations at r5491 | Confidence |
|---|---|---|---|---|---|
| G5 X | [r5186 / `2fc44f7d03bf650a6ac9bb6a9807d306783c795f`](https://github.com/01luna/CHDK/commit/2fc44f7d03bf650a6ac9bb6a9807d306783c795f), 2019-05-07T09:51:26Z | `100c`, full `101a`, `101b`, `101d`; compatibility-only `101c`, `101e`, `110a` | `DIGIC = 60`, `THUMB_FW=1`, DryOS R58 | `MEMBASEADDR=0x8000`; no ARAM heap override in platform makefile | HIGH for source state |
| EOS M10 | [r4755 / `bf72075c9024972fb9fc7a24eb2165a02aa2f72f`](https://github.com/01luna/CHDK/commit/bf72075c9024972fb9fc7a24eb2165a02aa2f72f), 2017-01-21T11:02:09Z | full `110d`, `110f`; compatibility-only `110g` | `DIGIC = 60`, `THUMB_FW=1`, DryOS R57 | `MEMBASEADDR=0x8000`; declares an ARAM heap but no forced ARAM policy | HIGH for source state |
| G16 | [r4958 / `702c763586f532aa20e0c5852c24f9cd98241648`](https://github.com/01luna/CHDK/commit/702c763586f532aa20e0c5852c24f9cd98241648), 2017-12-12T04:05:25Z | `100h`, `101a`, `101b`, `101c` | `DIGIC = 60`, `THUMB_FW=1`, DryOS R52 | `MEMBASEADDR=0x8000`; declares an ARAM heap; FI2 disabled by `override OPT_FI2=` | HIGH for source state |
| SX710 HS | [r4936 / `31815cbdafba30a064aa2a080cd12450bd2414dc`](https://github.com/01luna/CHDK/commit/31815cbdafba30a064aa2a080cd12450bd2414dc), 2017-12-05T04:26:28Z | `100a`, `101a` | `DIGIC = 60`, `THUMB_FW=1`, DryOS R57 | `MEMBASEADDR=0x8000`; forces ARAM allocator on but explicitly does not place CHDK in ARAM | HIGH for source state |
| G3 X (forum-generated stub excerpt only) | No trunk platform directory found | ranma discussed `110e` and `120a` | DIGIC 6 is independently official; ranma's generated-stub excerpt labels DryOS R57 | Patch unavailable; memory policy and complete build metadata unknown | HIGH for DIGIC 6; MEDIUM for forum-reported R57; UNKNOWN otherwise |

The source declarations are visible in each r5491 [`makefile.inc`](https://github.com/01luna/CHDK/tree/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/platform). Generated `stubs_entry.S` headers independently label G5 X 100C as R58, M10 110D and SX710 101A as R57, and G16 100H as R52. The G3 X R57 label is preserved in ranma's generated-stub diff in [post 143438](https://chdk.setepontos.com/d/12600-g3-x-100c-fw-dump/22); without the patch or a permitted firmware analysis it is not independently reproduced here.

## Verified similarities

At r5491, all four reference ports:

- declare DIGIC 6 (`DIGIC = 60`), Thumb firmware (`THUMB_FW=1`), DryOS, ROM base `0xFC000000`, and memory base `0x8000` in their platform `makefile.inc`;
- use `platform/<camera>/` for camera-wide input, display, shooting, and feature configuration, and `platform/<camera>/sub/<firmware>/` for firmware-specific boot code and stubs;
- install a `CreateTask` redirection in firmware-specific `boot.c`, create CHDK's `SpyTask`, substitute `mykbd_task` for the physical-switch task, and signal `core_spytask_can_start` from a replacement file-module initialization task;
- contain generated and hand-maintained symbol layers: `stubs_auto.S`, `stubs_entry.S`, `stubs_entry_2.S`, and `stubs_min.S`, with generated function CSVs;
- explicitly retain camera- and firmware-specific constants and copied firmware fragments. Their shared architecture is therefore a workflow template, not evidence that any address or fragment is reusable on G3 X.

## Verified differences

### DryOS and boot configuration

DryOS release differs: G5 X is R58; M10 and SX710 are R57; G16 is R52. Encoded-diskboot keys, platform IDs, maximum RAM declarations, and ARAM policy also differ. G16 disables FI2 in its platform makefile, whereas the G3 X author reported a `task_TricInitTask` FI2 workaround. This makes G16 useful as a source-structure reference but directly contradicts treating its boot configuration as a G3 X template.

### Active task substitutions in representative r5491 boot files

This table records active replacement clauses, not commented examples:

| Port / path | Active task substitutions observed |
|---|---|
| [`g5x/sub/100c/boot.c`](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/platform/g5x/sub/100c/boot.c) | capture sequence, exposure driver, file write, Tric initialization, file-module initialization; physical switch is replaced later in startup. Movie and develop-sequence clauses are commented out. |
| [`m10/sub/110d/boot.c`](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/platform/m10/sub/110d/boot.c) | capture sequence, exposure driver, Tric initialization, a camera-specific Cocoa task, movie record, and file-module initialization; physical switch later. File-write/develop clauses are commented out and no `filewrite.c` exists. |
| [`g16/sub/100h/boot.c`](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/platform/g16/sub/100h/boot.c) | capture sequence, exposure driver, file-module initialization, and file write; physical switch later. Develop and movie clauses are inside `FIXME` comments. |
| [`sx710hs/sub/101a/boot.c`](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/platform/sx710hs/sub/101a/boot.c) | capture sequence, exposure driver, file write, Tric initialization, and file-module initialization; physical switch later. Develop is marked unnecessary and movie is not implemented. |
| G3 X, reported only | ranma named only physical switch, file-module initialization, file write, and Tric initialization in [post 143437](https://chdk.setepontos.com/d/12600-g3-x-100c-fw-dump/21). Implementations cannot be compared. |

The G3 X list overlaps most strongly with the G5 X/SX710 task names, but that is a similarity in intended hook roles only. It does not verify hook sites, calling conventions, task identity, or code compatibility.

### File modules and PTP file write

All four reference ports replace the file-module initialization task so `core_spytask_can_start` can be signalled after filesystem initialization. G5 X, G16, and SX710 additionally have firmware-specific `filewrite.c`, define a camera-specific `fwt_data_struct`, include `platform/generic/filewrite.c`, and actively redirect `task_FileWrite`. M10 has neither a `filewrite.c` nor an active file-write hook at this revision. The G3 X author's statement that `task_FileWrite` supported PTP remote file write verifies the intended role, but the unavailable source prevents structural validation.

### Platform-specific surface

Each reference port has camera-wide `kbd.c`, `lib.c`, `main.c`, `platform_camera.h`, `platform_kbd.h`, `shooting.c`, and `wrappers.c`. These encode button maps, viewport/bitmap/raw-buffer access, shooting-mode and exposure tables, feature flags, and wrappers. The files contain port-specific TODOs and qualifications even in established ports—for example unverified viewport/file-write details in G5 X, untested focus items in M10, scene-mode caveats in G16, and incomplete propset/display assumptions in SX710. Copying one directory cannot establish correct G3 X behavior.

## Source-level dependency map for a hypothetical G3 X port

This is a dependency map of work products, not a proposed patch and not a memory map.

| Layer | Depends on | Evidence-supported output | G3 X status |
|---|---|---|---|
| Build identity | verified camera model, firmware revision, DryOS release, loader/encoding facts | `platform/g3x/makefile.inc`, per-revision `sub/*/makefile.inc`, compatibility declarations | DryOS R57 is author-reported; all other exact values must be recovered or independently derived later. |
| Generated symbol layer | legally obtained private firmware analysis in an approved later phase; CHDK signature tools and manual review | `stubs_auto.S`, `stubs_entry.S`, function CSVs | Missing. Never infer addresses from another camera. |
| Reviewed symbol overrides | generated symbols plus manual semantic verification | `stubs_entry_2.S`, `stubs_min.S` | Missing. |
| Boot integration | verified startup flow, memory ownership, loader path, task-creation ABI | firmware-specific `boot.c`; safe CHDK allocation; SpyTask creation | Historical patch reportedly booted, but its code and allocation policy are unavailable. |
| Minimal runtime hooks | verified original task identities and continuation semantics | keyboard/physical-switch replacement; file-module start signal; optional file-write and Tric hooks | Four roles are author-reported; no implementation is verified. |
| Camera-wide platform layer | verified hardware/UI behavior and buffers | `kbd.c`, `lib.c`, `main.c`, `platform_camera.h`, `platform_kbd.h`, `shooting.c`, `wrappers.c` | Exact contents unknown because patch is unavailable. |
| Capture features | verified capture task and exposure path | `capt_seq.c`, exposure overrides, raw hook | Not among ranma's reported minimum hooks; unknown/missing. |
| File-transfer support | verified file-write task state machine and data structure | `filewrite.c` plus generic file-write glue | Role reported, implementation unknown. M10 demonstrates this layer is optional, not universal. |
| Movie features | verified movie task/state machine and safety analysis | `movie_rec.c` only if required and proven | No G3 X implementation claim; reference ports vary and some explicitly leave this unimplemented. |
| Display/live view | verified viewport, bitmap, palette, HDMI mode behavior, bounds | camera-specific `lib.c`/`main.c` and guarded mode handling | Historical instability is unresolved; no allocation or address may be reused. |
| Validation | later explicit authorization, reproducible build provenance, then staged non-hardware checks before any camera work | source review, build-only checks, eventual hardware plan | Outside Phase 0. |

The narrowest defensible plan is therefore: recover the text patch first; identify its base from patch preimages; inventory its platform and subdirectory files; compare each role against the r5491 reference trees; and defer every address, memory-region, ABI, or binary-compatibility claim until independently supported.

## Historical HDMI and RAM-relocation evidence

- In [post 143433](https://chdk.setepontos.com/d/12600-g3-x-100c-fw-dump/18), 2020-05-11T11:03:54Z, ranma reported live-view crashes especially in 1080p over HDMI, usually within about a minute, and offered memory pressure or timing only as possibilities.
- In [post 143435](https://chdk.setepontos.com/d/12600-g3-x-100c-fw-dump/19), 2020-05-11T20:06:06Z, srsa_4c explicitly described an overlay-buffer overrun explanation as a guess because source, dump, and ROM log details were not supplied.
- In [post 143436](https://chdk.setepontos.com/d/12600-g3-x-100c-fw-dump/20), 2020-05-11T22:11:20Z, ranma said relocating “ARAM” and enabling CHDK from it *seemed* to resolve instability, immediately qualifying this with “needs more testing.” The claimed unused range and Xtensa ownership were themselves described as apparent/probable, and the author said heap boundaries needed double-checking.

Classification: **verified historical report; unvalidated mechanism and unvalidated remedy**. No memory region from the post is approved for reuse, and the destructive startup RAM-writing experiment described there must not be repeated in Phase 0.

## Unresolved questions

- What exact CHDK revision produced the missing patch? r5491-r5492 only brackets publication; neither is established as the base.
- Which reference-port files and hunks were actually copied or adapted?
- What allocation policy did `g3x_110e.patch` use before and after the reported relocation?
- Did the patch contain capture, exposure, movie, display, or shooting-table work beyond the four reported active hooks?
- Was HDMI instability caused by memory overlap, display bounds, timing, another subsystem, or multiple causes?
- Can an authorized person provide the original text patch, with provenance, without providing any firmware binary?

## Reproducible read-only checks

```sh
tmpdir=$(mktemp -d /tmp/g3x-chdk-archaeology.XXXXXX)
git clone --filter=blob:none --no-checkout https://github.com/01luna/CHDK.git "$tmpdir/CHDK"
git -C "$tmpdir/CHDK" show -s --format='%H%n%aI%n%B' 21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6
git -C "$tmpdir/CHDK" diff --name-status 21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6 8cded093bccce82ffe34d904da640fc55e087314
git -C "$tmpdir/CHDK" ls-tree -r --name-only 21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6 -- platform/g5x platform/m10 platform/g16 platform/sx710hs
```

The clone is source text only and was used for inspection, not built or executed.
