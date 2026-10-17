# Canon PowerShot G3 X GM1.10C ROM analysis

Updated: 2026-10-17  
Scope: Phase 2, offline read-only analysis  
Input: local owner-acquired `firmware/dumps/GM1.10C/PRIMARY.BIN` (never committed or uploaded)

## Executive result

The acquired image passes the expected size and SHA-256 checks and contains internally consistent G3 X, `GM1.10C`, DryOS R57, Canon build, ARM-toolchain, and DIGIC-6-style ROM markers. Its bytes were unchanged before and after analysis. Direct opcode evidence establishes a small ARM-state bootstrap that switches to Thumb state; most early executable bytes have Thumb/Thumb-2 encoding patterns. A complete reset path, exception-vector table, segment permissions, RAM-copy map, and function boundaries remain unresolved pending controlled disassembly.

The file is not uniformly populated. There is a large `0xFF` gap from file offsets `0x00EF63E8` through `0x012FFFFF`, plus several later erased-looking gaps and zero-filled regions. High-entropy late regions may contain compressed or encoded assets, but entropy alone does not identify compression, encryption, or executable code.

## 1. Provenance and immutable checks

| Check | Observed | Result |
|---|---:|---|
| File size | `33,554,432` bytes (`0x02000000`, 32 MiB) | confirmed |
| SHA-256 | `9911855772e433c877a9914f16d3735e15a48ca63352633e8f10364182912578` | matches owner metadata |
| Assumed dump base | `0xFC000000` | consistent with CHDK DIGIC 6 dumper and in-image pointers |
| Mapped range under that base | `0xFC000000`–`0xFDFFFFFF` inclusive | arithmetic result, not a CPU permission map |
| Whole-image Shannon entropy | `5.281617` bits/byte | measured by `tools/analyze_rom.py` |
| Input metadata during analysis | inode, size, and nanosecond mtime unchanged | confirmed |
| Git exclusion | `.gitignore` rule `firmware/*` matches both directory and dump | confirmed with `git check-ignore -v` |

The Canon Basic log is 26 bytes and was owner-reported as `Started / FC000000 dry / done`. The analyzer does not consume or depend on that log.

Reproduction:

```sh
python3 tools/analyze_rom.py \
  firmware/dumps/GM1.10C/PRIMARY.BIN \
  --base 0xFC000000 \
  --expect-size 0x2000000 \
  --expect-sha256 9911855772e433c877a9914f16d3735e15a48ca63352633e8f10364182912578 \
  > /tmp/g3x-gm110c-analysis.json
```

The script uses only the Python standard library, opens the image as `rb`, maps it with `mmap.ACCESS_READ`, emits JSON to standard output, and returns nonzero on an expected-size/hash mismatch or input metadata change. It deliberately does not disassemble, identify functions, or write beside the ROM.

## 2. Direct identity and firmware metadata

Offsets below are file offsets; add `0xFC000000` to obtain the candidate ROM address.

| File offset | Candidate ROM address | Evidence | Interpretation |
|---:|---:|---|---|
| `0x00020004` | `0xFC020004` | ASCII `gaonisoy` | matches the DIGIC 6 branch in the audited CHDK Canon Basic dumper |
| `0x00255298` | `0xFC255298` | ASCII `GM1.10C` | internal revision marker |
| `0x0054E080` | `0xFC54E080` | `Firmware Ver GM1.10C` (`GM1.10C` begins at `0x0054E08D`) | strongest build-identity string |
| `0x0054E044` | `0xFC54E044` | `Jul 22 2016`, followed by `11:47:27` | plausible firmware build timestamp; relationship to release date is unverified |
| `0x00616EA0`, `0x0062CAD8`, `0x00C9D8A0` | corresponding base-plus-offset addresses | `DRYOS version 2.3, release #0057` | direct DryOS R57 evidence |
| `0x0062CA79` and others | corresponding addresses | `Copyright (C) 1997-2014 by CANON Inc.` | Canon firmware content |
| `0x0062D00D` | `0xFC62D00D` | `[platform]=ARM(RVCT4.0[Build 902])` | ARM RealView toolchain marker |
| `0x01DC2E70` | `0xFDDC2E70` | `G3X-831_Canon0B` | G3 X-specific asset/metadata marker |
| `0x01F20410` and many localized copies after `0x01F60000` | corresponding addresses | `Canon PowerShot G3 X` | model identity |

The platform ID `0x32A8` is externally verified from the camera. Five byte occurrences of little-endian `A8 32 00 00` exist in the ROM, but four are visibly members of monotonically increasing numeric tables and the remaining occurrence is not yet tied to a platform-ID consumer. Therefore no ROM address for `PLATFORMID` is claimed.

## 3. Architecture, instruction states, and candidate entries

### Confirmed

- The first two little-endian words are `0xFC004510` and `0xFC00467C`, both inside the dumped address range.
- At `0xFC004510`, bytes decode as classic 32-bit ARM instructions:
  - `04 00 8F E2` → `ADD r0, pc, #4`
  - `01 00 80 E3` → `ORR r0, r0, #1`
  - `10 FF 2F E1` → `BX r0`
- Setting address bit 0 before `BX` changes execution to Thumb state. Bytes immediately after this trampoline and in the image header contain recognizable Thumb/Thumb-2 encodings, including `0x4770` (`BX LR`) and 32-bit Thumb instruction prefixes.
- The firmware is therefore not correctly modeled as ARM-only. A Ghidra project should start with ARM little-endian and permit Thumb context, with most discovered function entry points expected to carry/require Thumb state.

### Candidate, not yet confirmed

- `0xFC004510` is a candidate early bootstrap entry because the ROM header points to it and it performs a state transition. The source of the initial branch into the header is unknown.
- `0xFC00467C` currently appears to begin a numeric configuration table. It must not be marked executable merely because the second header word points to it.
- Executable bytes occur from `0xFC000008` onward, but `0xFC000008` has not been established as the hardware reset entry.

### Unresolved

- No standard ARM vector table has been proven at `0xFC000000` or `0xFC020000`.
- Exception handlers, reset source, MMU mappings, RAM relocation records, and inter-core images remain unknown.
- Exact ARM architecture profile/core name is not established by these bytes alone. “DIGIC 6” is Canon product evidence; it is not by itself a CPU-core specification.

## 4. Structural and entropy results

The analyzer measured 64 KiB blocks and all uniform-byte runs of at least 4 KiB. Important observations:

- The main `0xFC100000`–`0xFC5FFFFF` blocks have average block entropy near `7.07`–`7.11` bits/byte and many ROM-pointer-like words, consistent with mixed compiled code and dense data.
- `0xFC600000`–`0xFCEFFFFF` becomes progressively more zero-heavy and structurally varied, consistent with tables/resources/padding mixed with code. This is a hypothesis, not a permission map.
- The exact `0xFF` run `0xFCEF63E8`–`0xFD2FFFFF` is `0x409C18` bytes long and is the largest erased-looking region.
- The exact `0xFF` run `0xFDAC63B4`–`0xFDCBFFFF` is `0x1F9C4C` bytes long.
- Other large `0xFF` runs include `0xFD362DA8`–`0xFD4ED61F` (`0x18A878`) and `0xFD5121D8`–`0xFD61FFFF` (`0x10DE28`).
- The final `0x20000` bytes, `0xFDFE0000`–`0xFDFFFFFF`, are all `0xFF`.
- The largest measured zero run is `0xFC94B93C`–`0xFC95D4D4` (`0x11B99` bytes). Zero runs may be alignment, sparse resource space, or serialized empty storage; they are not evidence of RAM/BSS because this is a ROM dump.
- Highest-entropy 64 KiB blocks include offsets `0x00AA0000` (`7.970768`) and `0x01E60000` (`7.943895`). These deserve format inspection. High entropy is not proof of encryption or compression.

See `docs/GM110C_MEMORY_MAP.md` for the evidence-bounded map.

## 5. GM1.10E information: usable versus unsafe

The original `g3x_110e.patch` remains unavailable, so there is no auditable G3 X source tree to apply. The strongest `GM1.10E` evidence remains ranma's primary forum posts and generated-stub excerpts.

Safe reference information:

- G3 X `GM1.10E` was reported as DryOS R57 and a DIGIC 6 port.
- The port used CHDK's DIGIC 6 task-hook architecture and named `task_PhySw`, `task_InitFileModules`, `task_FileWrite`, and `task_TricInitTask` as its minimal hooks.
- Ranma found G5 X most useful as a starting structure, with M10 and G16 also useful; reyalp specifically identified SX710 and M10 as other R57 ports.
- CHDK file organization, signature-finder workflow, task roles, and Ghidra version-tracking methodology can guide analysis.

Unsafe to transfer without GM1.10C proof:

- Every function, hook, RAM, heap, GPIO, overlay, palette, and task address.
- Stub tables and structure offsets.
- Allocation bounds or HDMI/live-view workarounds.
- Binary compatibility or patch applicability.

The dump gives a concrete negative control: ranma's `GM1.10E` script checked `GM1.10E` at `0xFC54E0B5`, while this `GM1.10C` image stores `GM1.10C` at `0xFC54E08D`; at `0xFC54E0B5`, GM1.10C instead contains part of `CheckSum Skip (no %s)`. Even this nearby build has shifted data, directly demonstrating why `110E` addresses cannot be copied.

Primary historical source: [CHDK G3 X forum discussion](https://chdk.setepontos.com/d/12600-g3-x-100c-fw-dump), especially ranma posts 143433, 143437, and 143438, retrieved 2026-10-17. CHDK mirror reference revision: r5491, commit [`21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6`](https://github.com/01luna/CHDK/tree/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6), retrieved 2026-10-17.

## 6. Safe macOS Intel tools

No new reverse-engineering package was installed or configured during this task.

| Tool | Read-only use | macOS Intel evidence / recommendation |
|---|---|---|
| `tools/analyze_rom.py` | hashes, entropy, fill runs, pointers, exact string offsets | preferred first gate; standard library only |
| `strings`, `xxd`, `shasum` | byte/string inspection and integrity | already available; no parser execution |
| CHDK `finsig_thumb2`, `capdis`, `find_eventproc`, `find_levent` | model-aware symbol candidates and Thumb disassembly | historically used on a G3 X dump; build only from pinned, reviewed CHDK source in a later bounded step |
| Capstone | disassembly backend for CHDK tools or independent validation | MacPorts reports `capstone @5.0.6` for Darwin. Prefer `sudo port install capstone` only after review; not installed here. [MacPorts port](https://ports.macports.org/port/capstone/details/), retrieved 2026-10-17 |
| Ghidra | interactive raw-binary mapping, ARM/Thumb context, cross references, version tracking | MacPorts locally reports `ghidra @12.1.4` with `openjdk25-zulu`; upstream master documents macOS x86-64 support with locally built native components and JDK 25 for Ghidra 12.2. Pin one released version and follow its bundled requirements. [MacPorts port](https://ports.macports.org/port/ghidra/details/), [upstream Getting Started](https://github.com/NationalSecurityAgency/ghidra/blob/master/GhidraDocs/GettingStarted.md), retrieved 2026-10-17 |
| Rizin/radare2 | optional independent raw disassembly | not necessary for the first workflow; avoid expanding the tool surface until Ghidra/CHDK results need corroboration |

## 7. First Ghidra workflow (proposed, not executed)

1. Recheck SHA-256 and copy the ROM into a second, Git-ignored analysis workspace. Keep the acquired original untouched.
2. Install one pinned Ghidra release through MacPorts or its official release path only after reviewing its exact JDK/native-component requirements. Record versions and hashes.
3. Create a non-shared local project under ignored `analysis-workspace/`; never put the dump or project in Git.
4. Import as **Raw Binary**, language **ARM little-endian**. Set the image block base to `0xFC000000`, length `0x02000000`, read-only. Do not assume the entire block is executable.
5. Initially disable broad auto-analysis. Define labels for proven strings and `0xFC004510`; set ARM state at the trampoline and Thumb state after its `BX`. Inspect references before creating code elsewhere.
6. Split obvious all-`0xFF` gaps into non-executable/uninitialized-style blocks or remove execute permission. Treat zero-heavy and high-entropy ranges as unknown data until references or formats prove otherwise.
7. Run conservative disassembly from evidence-backed entry candidates. Review every disassembly conflict; do not force linear code through strings, pointer tables, or fill.
8. Generate CHDK `finsig_thumb2` output from a pinned source revision in a separate step. Import names as candidate labels with provenance, not truth. Check each critical symbol through references and function shape.
9. Import a reference R57 port (M10 or SX710) and optionally G5 X as separate programs for Version Tracking. Accept matches based on code/data evidence, never address equality.
10. Export only analyst-authored symbol tables, hashes, and documentation. Do not commit decompiler output, bulk disassembly, the ROM, or the Ghidra database.

## 8. Findings by confidence

### Confirmed

- Exact size/hash and unchanged input metadata.
- Dump-base consistency, `gaonisoy`, `GM1.10C`, G3 X, Canon, DryOS R57, and ARM RVCT strings.
- ARM bootstrap at `0xFC004510` switches to Thumb state.
- Multiple exact `0xFF` and `0x00` runs, including the major gaps listed above.
- GM1.10E's published version-string address does not point to the version string in GM1.10C.

### Hypotheses

- `0xFC004510` participates in the earliest boot path.
- `0xFC020000` begins the main DryOS firmware component.
- Dense early ranges are primarily code/rodata; later high-entropy ranges are compressed/encoded assets or secondary components.
- Late populated islands may include auxiliary-processor firmware or resource files.

### Unresolved questions

- What points to the initial ROM header, and where is the actual reset/vector table?
- Which precise ranges are executable, copied to RAM, compressed, or consumed by other cores?
- Where is the authoritative platform ID object and its consumer?
- What are the exact task entry points, heap bounds, overlay buffers, and file-module hooks on GM1.10C?
- Which GM1.10E functions remain structurally matchable after version tracking?

## 9. Safety conclusion

This work read the local dump only. It did not install tooling, build or execute firmware-related code, access a camera or SD card, generate a boot payload, modify the image, upload proprietary bytes, commit, or push.
