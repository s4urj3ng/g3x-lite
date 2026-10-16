# Phase 0C report — CHDK source archaeology

Updated: 2026-10-16  
Status: complete within the no-patch evidence boundary

## Outcome

Historical CHDK source archaeology establishes a useful porting workflow but no transferable G3 X addresses or binaries. At r5491-r5492, G5 X, M10, G16, and SX710 HS are all source-declared DIGIC 6 Thumb/DryOS ports. Only M10 and SX710 share the G3 X author's reported DryOS R57. Their task hooks, file-write support, boot options, RAM declarations, and platform TODOs differ enough that none is a binary-compatible template.

The detailed evidence and dependency map are in `docs/CHDK_PORT_COMPARISON.md`.

## Findings by confidence

### Verified

- r5491 is Git commit `21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6`, dated 2020-05-11T01:48:30Z; r5492 is `8cded093bccce82ffe34d904da640fc55e087314`, dated 2020-05-15T21:31:11Z.
- The four examined platform trees are byte-tree-identical across those revisions; the sole intervening change is `modules/gui_fselect.c`.
- Ranma named G5 X as the starting reference and M10/G16 as additional references. Reyalp pointed to M10/SX710 as DryOS R57 ports.
- Source declarations at r5491 identify G5 X as DryOS R58, M10 and SX710 as R57, and G16 as R52; all four declare DIGIC 6 and Thumb firmware.
- The shared source architecture includes platform-wide files, firmware-specific boot/stub files, a `CreateTask` patching pattern, SpyTask creation, keyboard replacement, and file-module initialization signalling.
- Hook sets are not uniform. M10 lacks an active file-write hook/file and has camera-specific Cocoa/movie handling; G16 disables FI2; G5 X/SX710 have file-write and Tric hooks but differ in allocation policy and other active tasks.
- Ranma reported four minimum G3 X hooks only: physical switch, file-module initialization, file write, and Tric initialization.
- Ranma reported HDMI 1080p live-view instability. The subsequent ARAM relocation was described only as seemingly successful and needing more testing.

### Plausible, not verified

- G5 X may be the closest source-organization reference because the original porter selected it as such. This is informed author judgment, not compatibility proof.
- M10/SX710 R57 code may help identify semantic patterns in a future independently derived G3 X analysis. Matching OS release alone does not establish identical functions, addresses, layouts, or task behavior.
- Memory pressure or overlay corruption may have contributed to HDMI instability. The forum participants expressly framed these as possibilities/guesses.

### Unknown

- The exact base revision, file inventory, hunk content, and allocation choices of `g3x_110e.patch`.
- Any G3 X function address, hook address, memory ownership boundary, task ABI, or compatibility with a reference camera.
- Whether the reported relocation actually fixed HDMI instability or merely changed its frequency.

## Patch mirror search

No legitimate text-only mirror was found on 2026-10-16.

Checks performed:

- Exact-filename web queries for `g3x_110e.patch`, including CHDK forum, GitHub, and SourceForge scopes, returned no indexed result.
- GitHub repository search for the exact term returned zero repositories.
- GitHub code search could not be evaluated anonymously because the API requires authentication; no access control was bypassed.
- grep.app returned HTTP 429, so it supplied no evidence either way.
- The original forum attachment remains identified as post 143437 / legacy attachment 16495 / migrated UUID `51fc3fb9-0f60-456b-ae9c-d090c1a1c176`; guest download remains unavailable as documented in `docs/PATCH_AUDIT_110E.md`.

Absence from these indexes is not proof that no mirror exists. No firmware archive or executable content was requested or downloaded.

## Safety accounting

Completed actions were limited to fetching public HTML/JSON text, cloning public CHDK source into a temporary directory, and reading Git history/source. No downloaded script was executed. CHDK was not built. No firmware binary, boot payload, camera, REA, Ghidra, or MCP configuration was used.

## Recommended next task

Keep Phase 0 bounded to artifact recovery: have an authorized human download only `g3x_110e.patch` from the forum or obtain the original text from ranma. Then record its measured byte size and SHA-256, verify it is plain text before reading, and determine the base revision from hunk preimages. Until that artifact exists, the next productive source-only task is a documented generic CHDK port-file checklist keyed to the dependency map—not implementation.

## Blockers

- Original patch bytes remain inaccessible to guest access and absent from the checked public indexes.
- Exact patch base and structure cannot be reconstructed from publication timing or reference-port sources.
- Firmware-derived G3 X facts cannot be independently checked without later explicit approval and a legally obtained private dump.
