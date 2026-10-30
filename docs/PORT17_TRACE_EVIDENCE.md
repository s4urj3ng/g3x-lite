# PORT-17 — Runtime Trace Evidence: Trace Ring Placement, Firmware File Stubs / Filesystem Readiness, and LED Control Route

**Date**: 2026-10-30  
**Target Platform**: Canon PowerShot G3 X (GM1.10C / Platform ID `0x32A8` = `12968` decimal)  
**Task ID**: `p17-trace-evidence` (Task 65)  
**Safety Scope**: Host-only static analysis and linker audit under the Phase 0 read-only safety model (`docs/SAFETY.md:1-8`). Zero ROM bytes were read or committed in this task. No camera hardware operations, flashing, binary modification, or code execution were performed (`docs/SAFETY.md:1-8`).

---

## 1. Executive Summary & Epistemic Framework

This document records primary-source and linker-backed evidence for the G3X Lite GM1.10C port across three critical subsystems required for post-first-boot runtime telemetry:
1. **Section (a) — Trace Ring Placement**: Evaluation of boot prototype memory layout, linker script structure, and section mechanics using local candidate link-map evidence to determine whether a dedicated trace buffer (`.g3x_trace`, NOLOAD, fixed size) can reside within the prototype image without displacing `boot_witness` or `_end` when tracing is disabled.
2. **Section (b) — Firmware File Stubs & Filesystem-Ready Point**: Tracked audit of high-level stream file wrappers ("Fut" API), status of low-level file descriptor routines, and the 6-stage lifecycle model of the `InitFileModules` readiness gate.
3. **Section (c) — LED Control Routes**: Analysis of candidate physical indicators, contrasting the high-level `LEDDrive` firmware stub, the pre-kernel fatal `LEDDrv.c` API, and direct MMIO GPIO routes.
4. **Section 2 — Closure Inventory & Minimal Proposed ROM Ranges**: A disposition for every non-VERIFIED item, and bounded candidate ROM inspection slices (each $\le 512$ B, 1,064 B in total) with explicit Thumb-bit derivations.
5. **Section 3 — Open Questions**: Codified open questions (`Q-P17-01` through `Q-P17-13`) for subsequent code TODOs and milestones.

### Evidence Classification Rules
Every substantive claim in this document carries exactly one of the following epistemic labels accompanied by an exact `file:line` citation of a Git-tracked repository file:
- **`[VERIFIED: file:line]`**: Stated directly by Git-tracked repository files, verified linker maps, built symbol tables, or static ROM analysis documented in tracked evidence dossiers.
- **`[INFERRED: file:line]`**: Logically deduced from specific verified facts and defined architectural/compiler rules documented in cited tracked files. Inferred claims cite the exact tracked lines from which they are deduced.
- **`[UNKNOWN: file:line]`** or **`[UNKNOWN]`**: Not established by tracked repository evidence. Uncited addresses, uninspected ROM sequences, and dynamic runtime hardware behaviors are strictly labeled `UNKNOWN`.

### Provenance Check
In strict adherence to project provenance standards, every file cited in this document has been confirmed to be tracked by Git (`git ls-files --error-unmatch <path>`):
- `docs/SAFETY.md` (Git-tracked)
- `docs/HANDOFF.md` (Git-tracked)
- `docs/PROJECT_STATE.md` (Git-tracked)
- `docs/PORT16_WITNESS_ADDRESS.md` (Git-tracked)
- `docs/PORT16_CANDIDATE_BUILD.md` (Git-tracked)
- `docs/PORT16_FIRSTBOOT_U_TRIAGE.md` (Git-tracked)
- `docs/PORT14_Q_MEM03_BSS.md` (Git-tracked)
- `docs/PORT11A_GM110C_ROM_EVIDENCE.md` (Git-tracked)
- `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md` (Git-tracked)
- `docs/RESTART_SD_HOST_AUDIT.md` (Git-tracked)
- `docs/PORT3A_RESTART_IRQ_AUDIT.md` (Git-tracked)
- `docs/HDMI001_OVERLAY_PIPELINE.md` (Git-tracked)
- `tools/build_candidate_port2a.py` (Git-tracked)
- `tools/port9a_runtime_lifecycle.py` (Git-tracked)
- `tools/port13_u2_obligations.py` (Git-tracked)
- `tools/port13_memory_obligations.py` (Git-tracked)
- `chdk-port/platform/g3x/sub/110c/boot_prototype.c` (Git-tracked)
- `chdk-port/platform/g3x/sub/110c/boot_witness.h` (Git-tracked)
- `chdk-port/platform/g3x/sub/110c/stubs_prototype.S` (Git-tracked)
- `vendor/g3x-platform/platform/g3x/lib.c` (Git-tracked)
- `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md` (Git-tracked)
- `firmware/tools/extend.m` (Git-tracked)
- `firmware/tools/witness_inspector_gm110c.m` (Git-tracked; cited as text only, never run or built)
- `docs/PORT13_MEMORY_OBLIGATIONS.md` (Git-tracked)
- `docs/PORT13_REVIEW_PR23.md` (Git-tracked)
- `docs/PORT5D_EARLY_BOOT_ROM_VERIFICATION.md` (Git-tracked)
- `docs/RESEARCH_LOG.md` (Git-tracked)
- `tools/validate_candidate_port2a.py` (Git-tracked; cited by name only, not run in this task)

Untracked files have zero evidentiary standing and are not used as sources; the one exception is the local candidate link map (and the untracked linker script status discussed in a.1), used only for link-layout facts in section (a). Claims without a tracked source are labeled `UNKNOWN`.

---

## Section (a): Trace Ring Placement & Memory Layout

### a.1 Boot Prototype Linker Layout & Tracked Linker Structure

The candidate relocated core is linked by `tools/build_candidate_port2a.py:279-299` using the GNU ld script passed as `"-Wl,-T,tools/link-boot.ld"` and `"-Wl,-N,-Ttext,0x3489b4"` (`tools/build_candidate_port2a.py:283-284`), with `-DMEMISOSTART=0x3489b4` (`tools/build_candidate_port2a.py:197`) `[VERIFIED: tools/build_candidate_port2a.py:197, 279-299]`. PORT-16 records the same link flags (`docs/PORT16_WITNESS_ADDRESS.md:108-109`) `[VERIFIED: docs/PORT16_WITNESS_ADDRESS.md:108-109]`.

**Tracking status of the linker script itself.** The script file `chdk-port/tools/link-boot.ld` is **not tracked by Git** (`git ls-files` returns no `*.ld` file anywhere in the repository, and `chdk-port/platform/g3x/sub/110c/` tracks only `boot_prototype.c`, `boot_witness.h` and `stubs_prototype.S`). Only its `.text`→`.data` clause (lines 14-26 of the untracked file) is quoted verbatim in a tracked document, `docs/PORT16_WITNESS_ADDRESS.md:270-287` `[VERIFIED: docs/PORT16_WITNESS_ADDRESS.md:270-287]`. No tracked file quotes the script's `.bss`, `_end` or `link_bss_end` clauses `[UNKNOWN: no tracked line; docs/PORT16_WITNESS_ADDRESS.md:270-287 stops at the end of the .data clause]`.

As quoted in tracked documentation (`docs/PORT16_WITNESS_ADDRESS.md:272-285`), the linker layout places `.data` contiguously immediately after `.text`:

```ld
    . = ALIGN(4);
    link_text_end = .;

    .data : {
	link_data_start = .;
    *(.rodata*)
    *(.rdata)
    . = ALIGN(4);
    *(.blob*)
	*(.data)
	. = ALIGN(4);
    }
```
`[VERIFIED: docs/PORT16_WITNESS_ADDRESS.md:270-287]`

Because the core is linked with `-N -Ttext 0x3489b4`, `.data` begins immediately at `link_text_end` (`docs/PORT16_WITNESS_ADDRESS.md:289-291`) `[VERIFIED: docs/PORT16_WITNESS_ADDRESS.md:289-291]`.

What the tracked script quote **mandates** (VERIFIED from `docs/PORT16_WITNESS_ADDRESS.md:272-285` only):
- `. = ALIGN(4); link_text_end = .;` before `.data` (`docs/PORT16_WITNESS_ADDRESS.md:273-274`) `[VERIFIED]`.
- Inside `.data`: `link_data_start = .;`, then `*(.rodata*)`, `*(.rdata)`, `. = ALIGN(4);`, `*(.blob*)`, `*(.data)`, `. = ALIGN(4);` in that order (`docs/PORT16_WITNESS_ADDRESS.md:277-285`) `[VERIFIED]`.

What is **not** mandated by any tracked script line:
- The 16-byte alignment of `boot_witness` comes from the C attribute `__attribute__((aligned(16), section(".data")))` (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:27`), not from the linker script `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:27]`.
- The `.bss` section order, any `. = ALIGN (0x10)` before `_end`, and the `_end`/`link_bss_end` assignments appear only in the local, uncommitted link map (Excerpt 4 below) `[INFERRED: local candidate_port2a/candidate_main.map; build-specific]`. Tracked files record only the resulting values: `_end = 0x00366CB0` and `link_bss_end = 0x00366CB0` (`docs/PORT16_CANDIDATE_BUILD.md:250-251`; `docs/PORT16_WITNESS_ADDRESS.md:218`) and the builder's fallback/heap-base value `0x00366CB0` (`tools/build_candidate_port2a.py:412, 742, 784`), which are addresses, not alignment directives `[VERIFIED: docs/PORT16_CANDIDATE_BUILD.md:250-251; tools/build_candidate_port2a.py:412, 742, 784]`.
- `new_sa` is commented as "the 16-byte aligned end of CHDK BSS" (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:23-24`); this comment is consistent with, but does not prove, a script-level `ALIGN(16)` `[INFERRED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:23-24]`.

### a.2 Local Candidate Build Link Map Evidence

To establish empirical ground truth without altering tracked Git state, a local candidate build was executed on the host, generating an uncommitted local linker map file.

#### Build Execution Record
- **Build Command**:
  ```bash
  python3 -B tools/build_candidate_port2a.py
  ```
  Followed by linking with map generation (as documented in `docs/PORT16_WITNESS_ADDRESS.md:104-122`):
  ```bash
  cd chdk-port && ../toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-gcc \
      -nostdlib \
      -Wl,--allow-shlib-undefined \
      -Wl,-T,tools/link-boot.ld \
      -Wl,-N,-Ttext,0x3489b4 \
      -Wl,-Map,../candidate_port2a/candidate_main.map \
      -o ../candidate_port2a/candidate_main.elf \
      -Wl,--start-group \
      platform/g3x/sub/110c/entry.o \
      platform/g3x/libplatform.a \
      ../candidate_port2a/libplatformsub_candidate.a \
      lib/font/.o2/libfont.a \
      lib/math/.o2/libmath.a \
      lib/lang/.o2/liblang.a \
      lib/armutil/.o2/libarmutil.a \
      lib/core/.o2/libcore.a \
      -lgcc \
      -Wl,--end-group
  ```
- **Git Base SHA**: `2583594`
- **Local Map Path (uncommitted, local only)**: `candidate_port2a/candidate_main.map`

#### Quoted Map Excerpt 1: `.text` End, Boundary, and `.data` Start
```text
.rel.dyn        0x0035aec0        0x0
 .rel.iplt      0x0035aec0        0x0 platform/g3x/sub/110c/entry.o
                0x0035aec0                . = ALIGN (0x4)
                0x0035aec0                link_text_end = .

.data           0x0035aec0     0xa344
                0x0035aec0                link_data_start = .
 *(.rodata*)
 .rodata        0x0035aec0        0x4 platform/g3x/libplatform.a(main.o)
                0x0035aec0                zoom_points
```

#### Quoted Map Excerpt 2: `boot_witness` Placement & Alignment Padding
```text
 *(.blob*)
 *(.data)
 .data          0x0035f798        0x0 platform/g3x/sub/110c/entry.o
 .data          0x0035f798        0x0 platform/g3x/libplatform.a(main.o)
 .data          0x0035f798        0x0 platform/g3x/libplatform.a(lib.o)
 .data          0x0035f798        0x4 platform/g3x/libplatform.a(wrappers.o)
 *fill*         0x0035f79c        0x4 
 .data          0x0035f7a0       0x20 ../candidate_port2a/libplatformsub_candidate.a(boot_prototype.o)
                0x0035f7a0                boot_witness
 .data          0x0035f7c0        0x0 ../candidate_port2a/libplatformsub_candidate.a(stubs_prototype.o)
```

#### Quoted Map Excerpt 3: `.data` End, `.bss` Start, and Section Boundary
```text
 .data          0x003651f0       0x14 platform/g3x/libplatform.a(platform_palette.o)
                0x003651f0                ply_colors
 .data          0x00365204        0x0 lib/armutil/.o2/libarmutil.a(reboot.o)
 .data          0x00365204        0x0 lib/armutil/.o2/libarmutil.a(cache.o)
                0x00365204                . = ALIGN (0x4)

.igot.plt       0x00365204        0x0
 .igot.plt      0x00365204        0x0 platform/g3x/sub/110c/entry.o
                0x00365204                . = ALIGN (0x4)
                0x00365204                link_data_end = .

.bss            0x00365204     0x1aac
                0x00365204                link_bss_start = .
```

#### Quoted Map Excerpt 4: Image End, Padding Fill, and `_end` / `link_bss_end`
```text
 COMMON         0x00366c98        0x8 lib/core/.o2/libcore.a(versions.o)
                0x00366c98                chdk_version
 COMMON         0x00366ca0        0x4 platform/g3x/libplatform.a(kbd.o)
                0x00366ca0                physw0_override
                0x00366cb0                . = ALIGN (0x10)
 *fill*         0x00366ca4        0xc 
                0x00366cb0                _end = .
                0x00366cb0                . = ALIGN (0x10)
                0x00366cb0                link_bss_end = .
```

#### Numerical Comparison with Tracked PORT-16 Documents
Comparing the extracted values from the local candidate build map against tracked documentation (`docs/PORT16_WITNESS_ADDRESS.md` and `docs/PORT16_CANDIDATE_BUILD.md`):

| Boundary / Symbol | Local Map Value | Tracked PORT-16 Documented Value | Citation in Tracked Docs | Comparison Result |
|---|:---:|:---:|---|:---:|
| `_start` / `link_text_start` | `0x003489B4` | `0x003489B4` | `docs/PORT16_CANDIDATE_BUILD.md:163, 243-244` | Exact match (0 delta) |
| `link_text_end` | `0x0035AEC0` | `0x0035AEC0` | `docs/PORT16_WITNESS_ADDRESS.md:216, 294-308; docs/PORT16_CANDIDATE_BUILD.md:246` | Exact match (0 delta) |
| `link_data_start` | `0x0035AEC0` | `0x0035AEC0` | `docs/PORT16_WITNESS_ADDRESS.md:216, 294-308; docs/PORT16_CANDIDATE_BUILD.md:245` | Exact match (0 delta) |
| Pre-witness padding | `0x0035F79C` (4 B) | `0x0035F79C` (4 B) | `docs/PORT16_WITNESS_ADDRESS.md:169, 187` | Exact match (0 delta) |
| `boot_witness` | `0x0035F7A0` | `0x0035F7A0` | `docs/PORT16_WITNESS_ADDRESS.md:15-16, 171, 213; docs/PORT16_CANDIDATE_BUILD.md:23, 163, 208, 247` | Exact match (0 delta) |
| `link_data_end` | `0x00365204` | `0x00365204` | `docs/PORT16_WITNESS_ADDRESS.md:217; docs/PORT16_CANDIDATE_BUILD.md:249` | Exact match (0 delta) |
| `link_bss_start` | `0x00365204` | `0x00365204` | `docs/PORT16_WITNESS_ADDRESS.md:217; docs/PORT16_CANDIDATE_BUILD.md:248` | Exact match (0 delta) |
| Pre-`_end` padding | `0x00366CA4` (12 B) | Not recorded in any tracked doc | None (local uncommitted map only, Excerpt 4) | `INFERRED` (build-specific) |
| `_end` / `link_bss_end` | `0x00366CB0` | `0x00366CB0` | `docs/PORT16_WITNESS_ADDRESS.md:218; docs/PORT16_CANDIDATE_BUILD.md:24, 163, 228, 250-251` | Exact match (0 delta) |

**Conclusion on Map Alignment**: Every symbol value the tracked PORT-16 docs record agrees with the local link map `[VERIFIED: docs/PORT16_WITNESS_ADDRESS.md:15, 169, 187, 216-218; docs/PORT16_CANDIDATE_BUILD.md:243-251]`. The 12-byte pre-`_end` fill is observed only in the local, uncommitted map; it is build-specific and may change with the toolchain or the linked inputs `[INFERRED: local map only]`.

### a.3 Trace Ring Section Placement Analysis

Based on the linker script structure and the quoted map excerpts, the feasibility of placing a dedicated trace ring section (`.g3x_trace`, NOLOAD, fixed size $S$) is evaluated:

1. **Image Footprint Definition**:
   The candidate binary image spans from `_start` (`0x003489B4`) through `_end` (`0x00366CB0`), calculated as `MEMISOSIZE = (&_end - &_start)` (`tools/build_candidate_port2a.py:198; docs/PORT16_CANDIDATE_BUILD.md:163; docs/PORT16_WITNESS_ADDRESS.md:218`) `[VERIFIED: tools/build_candidate_port2a.py:198; docs/PORT16_CANDIDATE_BUILD.md:163; docs/PORT16_WITNESS_ADDRESS.md:218]`.

2. **Can a dedicated `.g3x_trace (NOLOAD, fixed size)` sit inside the prototype image without moving `boot_witness` or `_end` when tracing is OFF?**
   The impact of allocating a fixed non-zero buffer of size $S$ depends on buffer size, alignment, and placement relative to existing linker padding:
   - **Pre-`boot_witness` placement** (inside `.text` or `.data` before `0x0035F7A0`):
     - As shown in map Excerpt 2 and the tracked PORT-16 map quote (`docs/PORT16_WITNESS_ADDRESS.md:169, 187`), exactly 4 bytes of alignment fill (`*fill* 0x0035f79c 0x4`) exist immediately preceding `boot_witness` at `0x0035F7A0`; that fill results from `aligned(16)` on `boot_witness` (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:27`) `[VERIFIED: docs/PORT16_WITNESS_ADDRESS.md:169, 187; chdk-port/platform/g3x/sub/110c/boot_prototype.c:27]`.
     - A small reservation placed prior to `boot_witness` with size $S \le 4$ bytes and 4-byte alignment can consume this existing padding without advancing `boot_witness` or `_end` `[INFERRED: docs/PORT16_WITNESS_ADDRESS.md:169, 187, 270-287]`.
     - However, any reservation exceeding 4 bytes ($S > 4$) or requiring alignment that shifts the location counter past `0x0035F79C` cannot fit within this 4-byte padding and will push `boot_witness` beyond `0x0035F7A0`, as well as displacing downstream `.data`, `.bss`, and `_end` `[INFERRED: docs/PORT16_WITNESS_ADDRESS.md:169-187, 270-287; docs/PORT16_CANDIDATE_BUILD.md:247]`.
   - **Post-`boot_witness` placement** (inside `.data` after `0x0035F7A0`, between `.data` and `.bss`, or inside `.bss` before `_end`):
     - Placing an allocation after `boot_witness` preserves `boot_witness = 0x0035F7A0` `[INFERRED: docs/PORT16_WITNESS_ADDRESS.md:15-16, 171]`.
     - In the local, uncommitted map (Excerpt 4), `. = ALIGN (0x10)` precedes `_end = .` and `link_bss_end = .`, leaving 12 bytes (`0xC`) of fill (`*fill* 0x00366ca4 0xc`) between the last COMMON symbol (`physw0_override` at `0x00366CA0`) and `_end` at `0x00366CB0` `[INFERRED: local map only; build-specific]`. No tracked line quotes this `ALIGN (0x10)` clause (see a.1), so the alignment rule and the 12-byte hole are not tracked facts; tracked docs record only `_end = 0x00366CB0` (`docs/PORT16_WITNESS_ADDRESS.md:218; docs/PORT16_CANDIDATE_BUILD.md:250`) `[VERIFIED: docs/PORT16_WITNESS_ADDRESS.md:218; docs/PORT16_CANDIDATE_BUILD.md:250]`.
     - If the local map's rule holds, a reservation placed after `boot_witness` and before `_end` with size $S \le 12$ bytes (alignment $\le 4$) could consume this fill without advancing `_end` past `0x00366CB0` `[INFERRED: local map only; docs/PORT16_WITNESS_ADDRESS.md:218]`.
     - Any reservation with $S > 12$ bytes cannot be absorbed by that fill and will advance `_end = link_bss_end` to at least `0x00366CC0` (`ALIGN_UP(0x00366CA4 + S, 16)` under the local map's rule) `[INFERRED: local map only; docs/PORT16_WITNESS_ADDRESS.md:218]`.
   - **Post-`_end` placement** (`. > _end`):
     - Any memory above `_end` lies strictly **outside** the prototype image footprint (`MEMISOSIZE`) `[VERIFIED: tools/build_candidate_port2a.py:198; docs/PORT16_CANDIDATE_BUILD.md:163; docs/PORT16_WITNESS_ADDRESS.md:218]`.
     - Furthermore, `new_sa = &_end` (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:24`) is loaded into `r4` (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:172-174`) and stored as the DryOS heap base `sp[0x08]` (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:206-210`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:24, 172-174, 206-210]`. Memory immediately above `_end` is therefore handed to DryOS as heap and may be overwritten by kernel allocations `[INFERRED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:206-210]`.
   - **Conclusion on Fixed Non-Zero Size when Tracing is OFF**:
     - An unconditionally allocated section with fixed non-zero size cannot sit inside the prototype image without moving `boot_witness` or `_end`, UNLESS it fits strictly within the existing alignment padding: either $S \le 4$ bytes before `boot_witness` (consuming `0x0035F79C..0x0035F79F`, tracked), or $S \le 12$ bytes before `_end` (consuming `0x00366CA4..0x00366CAF`, local map only).
     - For any non-trivial trace ring buffer ($S \gg 12$ bytes, e.g. hundreds or thousands of bytes), it exceeds both padding holes; therefore, at least one of `boot_witness` or `_end` must move `[INFERRED: docs/PORT16_WITNESS_ADDRESS.md:169, 187, 218, 272-285; local map Excerpt 4]`.

3. **Conditionally Absent Section when Tracing is OFF**:
   - **What is VERIFIED (current baseline only)**: the current PORT-16 candidate layout, linked with the tracked flags (`tools/build_candidate_port2a.py:279-299`) and the tracked `.text`→`.data` script clause (`docs/PORT16_WITNESS_ADDRESS.md:270-287`), has `boot_witness = 0x0035F7A0` and `_end = link_bss_end = 0x00366CB0` `[VERIFIED: docs/PORT16_WITNESS_ADDRESS.md:15-16, 218, 270-287; docs/PORT16_CANDIDATE_BUILD.md:247, 250-251; tools/build_candidate_port2a.py:279-299]`. The local candidate map (a.2) shows only this baseline layout; no OFF-configuration layout with a `.g3x_trace` stanza has been linked or inspected.
   - **What is only INFERRED (not VERIFIED)**: that a tracing-OFF build leaves `boot_witness` at `0x0035F7A0` and `_end` at `0x00366CB0` `[INFERRED: docs/PORT16_WITNESS_ADDRESS.md:15-16, 218, 270-287; docs/PORT16_CANDIDATE_BUILD.md:247, 250]`. A zero-sized allocation alone is not enough: a retained `ALIGN()`, a `. = ...` location-counter assignment, or an output-section stanza that keeps its own alignment can still shift every later section. The inference holds only if all of the following are met:
     1. When `G3X_TRACE` is OFF, the whole `.g3x_trace` stanza is left out of the link: no output-section statement, no `ALIGN`, no location-counter assignment, no `KEEP`, and no reference symbols (for example `g3x_trace_start`/`g3x_trace_end`). This is done by preprocessor or by a separate linker fragment that is included only when tracing is ON.
     2. The OFF image is checked by comparing `boot_witness` and `_end` in the OFF link map against the PORT-16 values (`0x0035F7A0`, `0x00366CB0`; `docs/PORT16_WITNESS_ADDRESS.md:15, 218`; `docs/PORT16_CANDIDATE_BUILD.md:247, 250`).
     3. `candidate_validate` (`tools/validate_candidate_port2a.py`) passes on the OFF build, as it did for the PORT-16 baseline (`docs/PORT16_CANDIDATE_BUILD.md:22, 150, 183`).
   - These checks belong to task `p17-trace-core` and are tracked as `Q-P17-01` (section 3).

4. **Heap Headroom Constraint when Tracing is ON**:
   - When tracing is enabled (Tracing ON), placing `.g3x_trace` after `boot_witness` (e.g. between `.data` and `.bss` or at the end of `.bss` before `_end`) preserves `boot_witness = 0x0035F7A0` while allowing `_end` to expand by $\Delta = \text{ALIGN\_UP}(0x00366CA4 + S, 16) - 0x00366CB0$ `[INFERRED: docs/PORT16_WITNESS_ADDRESS.md:15-16, 217-218]`.
   - The early bootloader DryOS kernel headroom check evaluates `0x006CE000 - r4 >= 0x000B1FEC` (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:180-184`), where `r4 = new_sa = &_end` (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:173-174`).
   - The total remaining space between the DryOS heap limit (`0x006CE000`, `chdk-port/platform/g3x/sub/110c/boot_prototype.c:180; tools/build_candidate_port2a.py:213`) and baseline `_end` (`0x00366CB0`, `docs/PORT16_WITNESS_ADDRESS.md:218; docs/PORT16_CANDIDATE_BUILD.md:24, 250`) is:
     $$\text{remaining} = 0x006CE000 - 0x00366CB0 = 0x00367350 \text{ bytes (3,568,464 B, } \approx 3,484.8 \text{ KiB)}$$
     `[INFERRED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:180-184; docs/PORT16_WITNESS_ADDRESS.md:218]`.
   - The required minimum kernel headroom is:
     $$\text{required} = 0x000B1FEC \text{ bytes (729,068 B, } \approx 712 \text{ KiB)}$$
     `[VERIFIED as a prototype source constant: chdk-port/platform/g3x/sub/110c/boot_prototype.c:181]`; that GM1.10C ROM applies the same threshold is `[INFERRED: docs/PORT13_MEMORY_OBLIGATIONS.md:79]`.
   - To satisfy this static bootloader check, the conditional bound on section size $S$ is explicitly:
     $$S \le \text{remaining} - \text{required} = 0x00367350 - 0x000B1FEC = 0x002B5364 \text{ bytes (2,839,396 B, } \approx 2,772.8 \text{ KiB)}$$
     `[INFERRED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:180-184; docs/PORT16_WITNESS_ADDRESS.md:218]`.
   - **Actual runtime heap safety is `UNKNOWN`** `[UNKNOWN: chdk-port/platform/g3x/sub/110c/boot_prototype.c:179-186 is the only tracked check, and it is static]`. Shifting `_end` narrows the total available heap pool 0 (`sp[0x0C] = 0x00600014 - new_sa`, `chdk-port/platform/g3x/sub/110c/boot_prototype.c:209-210`), and static satisfaction of the early headroom check does not prove that subsequent dynamic DryOS kernel memory allocations or camera subsystems will not suffer heap starvation or heap collisions during runtime.

### a.4 Trace Ring Survival Across Soft Restart

- **Survival Status**: **`UNKNOWN`**. No tracked document proves retention; the nearest tracked evidence is listed below `[UNKNOWN: docs/PORT14_Q_MEM03_BSS.md:273, 282; docs/HANDOFF.md:979]`.
- **Tracked Evidence Audit**:
  - *Prototype BSS zeroing loop*: The boot prototype implementation clears memory from `0x0003F4F4` through `0x003489B3` (stopping strictly before `0x003489B4` = `MEMISOSTART`) (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:144-153`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:144-153]`.
  - *Canon GM1.10C ROM BSS zeroing behaviour*: The equivalence of the bounds notation is INFERRED for GM1.10C ROM (`docs/PORT14_Q_MEM03_BSS.md:270-271`), and tracked artifacts cannot decide the ROM zeroing-loop start address (`docs/PORT14_Q_MEM03_BSS.md:273, 282`); the loop instructions are recorded as "uninspected in ROM" (`tools/port13_memory_obligations.py:1013`) `[INFERRED: docs/PORT14_Q_MEM03_BSS.md:270-271; UNKNOWN: docs/PORT14_Q_MEM03_BSS.md:273, 282; tools/port13_memory_obligations.py:1013]`.
  - *Canon restart routine (identification)*: `docs/PORT3A_RESTART_IRQ_AUDIT.md:33` (finding F15) states: "Canon's restart routine `0xFC0D03E8` masks IRQ and calls bulk writer `0xFC0D9C52` (`0x0FFFFFFF` → `+0xC`) before `bx 0xFC020001`. Its only static caller uses mode 7, which returns without jumping." Its status column reads "V (code); U (reachability of the jump)". `docs/PROJECT_STATE.md:150` confirms: "**Canon warm-restart routine `0xFC0D03E8`:** calls `0xFC0D9C52` (a bulk `0x0FFFFFFF` write to `0xD401000C+16*i`) after masking IRQ. Its only static caller passes mode 7, which returns and does not jump to `0xFC020001`." The routine is therefore identified at `0xFC0D03E8` `[VERIFIED: docs/PORT3A_RESTART_IRQ_AUDIT.md:33; docs/PROJECT_STATE.md:150]`.
  - *Canon restart routine (behaviour)*: its code masks IRQ, calls `0xFC0D9C52` and ends in `bx 0xFC020001` `[VERIFIED (code): docs/PORT3A_RESTART_IRQ_AUDIT.md:33; docs/PROJECT_STATE.md:150]`. Whether that jump is ever reached is `UNKNOWN`: the only static caller passes mode 7, which returns without jumping `[UNKNOWN (reachability): docs/PORT3A_RESTART_IRQ_AUDIT.md:33; docs/PROJECT_STATE.md:150]`. Separately, the port's CHDK `Restart` stub is still a `NULL_SUB` (`docs/HANDOFF.md:979`) `[VERIFIED: docs/HANDOFF.md:979]`. That is a missing stub binding, not a missing routine identification. Neither tracked line addresses DRAM retention, so identifying the routine does not decide whether the ring survives.
  - *Soft-restart DRAM retention*: Memory at and above `0x003489B4` is outside the prototype zeroing loop (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:144-147`) `[VERIFIED]`. Whether DRAM contents survive the restart itself, and whether later DryOS heap initialization zeroes that memory, are not addressed by any tracked line; the only tracked restart-adjacent evidence covers the prototype loop (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:144-153`) and the undecided ROM loop (`docs/PORT14_Q_MEM03_BSS.md:282`) `[UNKNOWN: chdk-port/platform/g3x/sub/110c/boot_prototype.c:144-153; docs/PORT14_Q_MEM03_BSS.md:282]`.
  - No tracked repository document provides evidence or proof that DRAM contents in `0x003489B4..0x00366CB0` survive a soft restart. Therefore, soft-restart survival is classified as **`UNKNOWN`** (`Q-P17-02`).

### a.5 Tracked RAM Addresses Constraint

In accordance with strict project rules, no unverified firmware RAM address is proposed. The RAM addresses relevant to this task that tracked files cite are inventoried below (each citation re-checked against the exact line).

Rows of kind **Config** record a value written in prototype source or build configuration; they are VERIFIED only as "this is what the source/builder says". Rows of kind **FW/HW** record the separate claim that GM1.10C firmware or the camera hardware actually has that property, and carry their own label.

| RAM Address | Kind | Description / Role | Tracked Citation | Status |
|---|:---:|---|---|:---:|
| `0x00000000` | Config | Prototype copies the Thumb exception vector table from ROM `0xFC05B47C..0xFC05B4B4` to this address | `chdk-port/platform/g3x/sub/110c/boot_prototype.c:93-94` | `VERIFIED` |
| `0x00000000` | FW/HW | ATCM / exception vectors at address 0 on GM1.10C hardware | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:166` ("E: HISTORICALLY REPORTED") | `INFERRED` |
| `0x00004000` | Config | Initial boot stack pointer set by the prototype | `chdk-port/platform/g3x/sub/110c/boot_prototype.c:89-91` | `VERIFIED` |
| `0x00008000` | Config | `MEMBASEADDR` build define | `tools/build_candidate_port2a.py:196, 360, 395` | `VERIFIED` |
| `0x00008000` | FW/HW | Start of Canon low-RAM data on GM1.10C (`0x00008000–0x0003F4F3`) | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:167` ("SOURCE VERIFIED (both texts)", source text, not ROM) | `INFERRED` |
| `0x00008074..0x0000807C` | Config | Low-RAM words written by the prototype | `chdk-port/platform/g3x/sub/110c/boot_prototype.c:190-198` | `VERIFIED` |
| `0x00008074..0x0000807C` | FW/HW | Their role in GM1.10C firmware (DryOS heap check words, not hardware registers); ROM literal `0x00008074` is recorded at `0xFC05B60C` | `docs/PORT5D_EARLY_BOOT_ROM_VERIFICATION.md:36`; `docs/PORT16_WITNESS_ADDRESS.md:410` | `INFERRED` |
| `0x00009BA4` | FW/HW | `LEDDrv` runtime state word (`*0x00009BA4 == 0` pre-kernel → panic) | `docs/HANDOFF.md:509, 543; docs/PROJECT_STATE.md:223, 231` | `VERIFIED` |
| `0x0000C824` | FW/HW | Redraw-dispatch structure base (`+0x0C` task affinity, `+0x14` queue) | `docs/HANDOFF.md:1771` | `VERIFIED` |
| `0x00015DA4` | FW/HW | Palette LUT dirty flag | `docs/HDMI001_OVERLAY_PIPELINE.md:97` | `VERIFIED` |
| `0x0003F4F4` | Config | Start of the prototype BSS zeroing loop (`ldr r3, =0x0003f4f4`) | `chdk-port/platform/g3x/sub/110c/boot_prototype.c:144, 146` | `VERIFIED` |
| `0x0003F4F4` | FW/HW | IRQ handler table base (literal `0xFC0BAE1C`, class V in the tracked audit) | `docs/PORT3A_RESTART_IRQ_AUDIT.md:20` | `VERIFIED` |
| `0x0003F4F4` | FW/HW | Lower bound of the GM1.10C ROM BSS zeroing loop. `docs/PORT14_Q_MEM03_BSS.md:270-271`: "whether the `GM1.10C` hardware ROM early-boot zeroing loop itself uses these exact bounds remains **`INFERRED`**"; the loop start is undecided (`docs/PORT14_Q_MEM03_BSS.md:282`) | `docs/PORT14_Q_MEM03_BSS.md:270-271, 282; tools/port13_memory_obligations.py:1013` | `INFERRED` |
| `0x003489B4` | Config | `MEMISOSTART` build define, `-Ttext` link address, and exclusive stop of the prototype zeroing loop | `tools/build_candidate_port2a.py:197, 284; chdk-port/platform/g3x/sub/110c/boot_prototype.c:144-147` | `VERIFIED` |
| `0x003489B4` | FW/HW | Upper bound of the GM1.10C ROM BSS zeroing loop (same `INFERRED` qualification as above) | `docs/PORT14_Q_MEM03_BSS.md:270-271` | `INFERRED` |
| `0x003489B4` | FW/HW | Default (unshifted) DryOS heap base on GM1.10C; tracked memory obligation `OBLIG-MEM-05` is `INFERRED` | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:169; docs/PORT13_MEMORY_OBLIGATIONS.md:76` | `INFERRED` |
| `0x0035F7A0` | Config | Candidate `boot_witness` symbol address (host link output) | `docs/PORT16_WITNESS_ADDRESS.md:15; docs/PORT16_CANDIDATE_BUILD.md:23, 247` | `VERIFIED` |
| `0x00366CB0` | Config | Candidate `_end` / `new_sa` heap boundary symbol (host link output) | `docs/PORT16_WITNESS_ADDRESS.md:218; docs/PORT16_CANDIDATE_BUILD.md:24, 250` | `VERIFIED` |
| `0x00600014` | Config | Sub-pool 1 boundary written by the prototype into the DryOS setup structure | `chdk-port/platform/g3x/sub/110c/boot_prototype.c:209; tools/build_candidate_port2a.py:785` | `VERIFIED` |
| `0x00600014` | FW/HW | That GM1.10C DryOS uses this sub-pool boundary (`OBLIG-MEM-06`) | `docs/PORT13_MEMORY_OBLIGATIONS.md:77` | `INFERRED` |
| `0x0060E000` | Config | Heap pool 0 upper value written by the prototype (`sp[0x00]`) | `chdk-port/platform/g3x/sub/110c/boot_prototype.c:206` | `VERIFIED` |
| `0x0060E000` | FW/HW | That GM1.10C DryOS uses this pool bound (`OBLIG-MEM-07`) | `docs/PORT13_MEMORY_OBLIGATIONS.md:78` | `INFERRED` |
| `0x006CE000` | Config | Headroom-check limit in the prototype; `ARAM_HEAP_START` build define | `chdk-port/platform/g3x/sub/110c/boot_prototype.c:180; tools/build_candidate_port2a.py:213` | `VERIFIED` |
| `0x006CE000` | FW/HW | That GM1.10C ROM performs the same `0x006CE000 - r4 >= 0x000B1FEC` check (`OBLIG-MEM-08`) | `docs/PORT13_MEMORY_OBLIGATIONS.md:79` | `INFERRED` |
| `0x006F0000` | Config | ARAM heap upper bound (`0x006CE000 + 0x00022000`, arithmetic on build defines) | `tools/build_candidate_port2a.py:213-214` | `INFERRED` |
| `0x010E17A5` | FW/HW | SD1stInit task entry address | `docs/RESTART_SD_HOST_AUDIT.md:56; tools/port13_u2_obligations.py:802` | `VERIFIED` |
| `0x0FFFFFFF` | Config | `MAXRAMADDR` build define | `tools/build_candidate_port2a.py:200, 339` | `VERIFIED` |
| — | FW/HW | Physical DRAM size / upper boundary of the G3 X. A `MAXRAMADDR` define in the builder does not prove it; tracked docs note the bound is chosen from reference ports (`docs/RESEARCH_LOG.md:99`) and that no physical DRAM size evidence exists (`docs/PORT13_REVIEW_PR23.md:87`) | `docs/RESEARCH_LOG.md:99; docs/PORT13_REVIEW_PR23.md:87` | `UNKNOWN` |
| `0x40000000..0x7FFFFFFF` | FW/HW | "Region 1 alias" avoided by tracked loader code; `0x40000000` as uncached mirror is only historically reported | `docs/HANDOFF.md:410; docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:179` | `INFERRED` |
| `0x5FD00000` | FW/HW | Bitmap framebuffer device literal extracted from `BmpDev.c` | `docs/HANDOFF.md:995` | `VERIFIED` |
| `0xBFE14A3C` / `0xBFE14A3D` | FW/HW | TCM `hook_CreateTask` address / `CreateTask` entry | `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:49-50; docs/HANDOFF.md:978, 1025` | `VERIFIED` |
| `0xBFE14969` | FW/HW | TCM `SleepTask` entry address | `docs/HANDOFF.md:978, 1025` | `VERIFIED` |

Any other RAM address, including the `fileio_semaphore` and `file_counter_var` addresses, is strictly **`UNKNOWN`**; the only tracked stubs file defines no such symbol `[UNKNOWN: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49]`.

---

## Section (b): Firmware File Stubs & Filesystem-Ready Point

### b.1 Complete Tracked Inventory of Firmware File Stubs

Audit of Git-tracked repository documentation confirms the following firmware file stubs and internal filesystem entry points. Address evidence is separated from C parameter signatures and ABI calling conventions.

Existing stubs files: the only tracked stubs file for the port, `chdk-port/platform/g3x/sub/110c/stubs_prototype.S`, contains only the 41 `STUB(...)` boot-path entries at lines 9-49 and no file-I/O or LED stub `[VERIFIED: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49]`. Every row below whose address is `UNKNOWN` is therefore backed only by the absence of a stub in that tracked file `[UNKNOWN: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49]`.

Argument shapes: tracked Canon Basic scripts call the `Fut` wrappers by name as `Fopen_Fut(path, mode)` returning `0` on failure, `Fwrite_Fut(buf, size, count, fh)` and `Fclose_Fut(fh)` (`firmware/tools/extend.m:79-81, 89-93`), and `Fread_Fut(buf, 1, n, fh)` returning a byte count with `Fclose_Fut` returning `0` on success (`firmware/tools/witness_inspector_gm110c.m:100-117`) `[VERIFIED: firmware/tools/extend.m:79-81, 89-93; firmware/tools/witness_inspector_gm110c.m:100-117]`. These are event-procedure calls by name; that a direct C call to the `HANDOFF.md` addresses uses the same argument order is `[INFERRED: firmware/tools/extend.m:79-93]`, and the register ABI remains `UNKNOWN`.

| Function Stub | Address | Address Tracked Citation & Status | C Signature & ABI Calling Convention Status | Explanation of Status Separation |
|---|:---:|---|---|---|
| `Fopen_Fut` | `0xFC37EFA7` | `docs/HANDOFF.md:978, 1025` `[VERIFIED]` | **`UNKNOWN`** `[UNKNOWN: docs/HANDOFF.md:978, 1025]` | `docs/HANDOFF.md` verifies the entry address only. The `(path, mode)` argument shape and `0`-on-failure return are shown only for the Canon Basic by-name call (`firmware/tools/extend.m:79-80`; `firmware/tools/witness_inspector_gm110c.m:100-101`) `[INFERRED for direct C call]`; register ABI and full error codes remain uninspected in GM1.10C ROM. |
| `Fclose_Fut` | `0xFC37EFCF` | `docs/HANDOFF.md:1025` `[VERIFIED]` | **`UNKNOWN`** `[UNKNOWN: docs/HANDOFF.md:1025]` | Address verified; C argument types, file handle struct representation, and flush semantics uninspected in ROM. |
| `Fread_Fut` | `0xFC37F041` | `docs/HANDOFF.md:1025` `[VERIFIED]` | **`UNKNOWN`** `[UNKNOWN: docs/HANDOFF.md:1025]` | Address verified; C argument order (`buf, sz, cnt, fh`) and return byte-count semantics uninspected in ROM. |
| `Fwrite_Fut` | `0xFC37F077` | `docs/HANDOFF.md:1025` `[VERIFIED]` | **`UNKNOWN`** `[UNKNOWN: docs/HANDOFF.md:1025]` | Address verified; write buffering, synchronous/asynchronous write behavior, and error returns uninspected in ROM. |
| `Feof_Fut` | `0xFC37F111` | `docs/HANDOFF.md:1026` `[VERIFIED]` | **`UNKNOWN`** `[UNKNOWN: docs/HANDOFF.md:1026]` | Address verified; EOF sentinel values and error return convention uninspected in ROM. |
| `Fflush_Fut` | `0xFC37F139` | `docs/HANDOFF.md:1026` `[VERIFIED]` | **`UNKNOWN`** `[UNKNOWN: docs/HANDOFF.md:1026]` | Address verified; write cache synchronization behavior uninspected in ROM. |
| `GetDrive_TotalClusters` | `0xFC37AF8B` | `docs/HANDOFF.md:1026` `[VERIFIED]` | **`UNKNOWN`** `[UNKNOWN: docs/HANDOFF.md:1026]` | Address verified; drive number encoding and 32-bit/64-bit return layout uninspected in ROM. |
| Loader `open` | `0xFC37B4AE` | `docs/RESTART_SD_HOST_AUDIT.md:14` `[VERIFIED]` | **`UNKNOWN`** `[UNKNOWN: docs/RESTART_SD_HOST_AUDIT.md:14]` | Internal SD bootloader helper used by `StartDiskboot` (`docs/RESTART_SD_HOST_AUDIT.md:14`); calling convention and register arguments uninspected in ROM. |
| Loader `read` | `0xFC37B552` | `docs/RESTART_SD_HOST_AUDIT.md:14` `[VERIFIED]` | **`UNKNOWN`** `[UNKNOWN: docs/RESTART_SD_HOST_AUDIT.md:14]` | Internal SD bootloader helper used by `StartDiskboot` (`docs/RESTART_SD_HOST_AUDIT.md:14`); calling convention and sector alignment constraints uninspected in ROM. |
| Loader `close` | `0xFC37B4B0` | `docs/RESTART_SD_HOST_AUDIT.md:14` `[VERIFIED]` | **`UNKNOWN`** `[UNKNOWN: docs/RESTART_SD_HOST_AUDIT.md:14]` | Internal SD bootloader helper used by `StartDiskboot` (`docs/RESTART_SD_HOST_AUDIT.md:14`); calling convention uninspected in ROM. |
| `Open` | `UNKNOWN` | None; no stub in `chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49` `[UNKNOWN: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49]` | **`UNKNOWN`** `[UNKNOWN]` | Low-level DryOS open; address and ABI completely unverified in tracked files. |
| `Close` | `UNKNOWN` | None; no stub in `chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49` `[UNKNOWN: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49]` | **`UNKNOWN`** `[UNKNOWN]` | Low-level DryOS close; address and ABI completely unverified in tracked files. |
| `Write` | `UNKNOWN` | None; no stub in `chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49` `[UNKNOWN: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49]` | **`UNKNOWN`** `[UNKNOWN]` | Low-level DryOS write; address and ABI completely unverified in tracked files. |
| `Read` | `UNKNOWN` | None; no stub in `chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49` `[UNKNOWN: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49]` | **`UNKNOWN`** `[UNKNOWN]` | Low-level DryOS read; address and ABI completely unverified in tracked files. |
| `open` (POSIX) | `UNKNOWN` | None; no stub in `chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49` `[UNKNOWN: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49]` | **`UNKNOWN`** `[UNKNOWN]` | POSIX open wrapper; address and ABI completely unverified in tracked files. |
| `close` (POSIX) | `UNKNOWN` | None; no stub in `chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49` `[UNKNOWN: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49]` | **`UNKNOWN`** `[UNKNOWN]` | POSIX close wrapper; address and ABI completely unverified in tracked files. |
| `Fseek_Fut` | `UNKNOWN` | None; no stub in `chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49` `[UNKNOWN: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49]` | **`UNKNOWN`** `[UNKNOWN]` | High-level seek wrapper; address and ABI completely unverified in tracked files. |
| `Fgets_Fut` | `UNKNOWN` | None; no stub in `chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49` `[UNKNOWN: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49]` | **`UNKNOWN`** `[UNKNOWN]` | High-level string read; address and ABI completely unverified in tracked files. |
| `MakeDirectory_Fut` | `UNKNOWN` | None; no stub in `chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49` `[UNKNOWN: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49]` | **`UNKNOWN`** `[UNKNOWN]` | Directory creation wrapper; address and ABI completely unverified in tracked files. |
| `DeleteFile_Fut` | `UNKNOWN` | None; no stub in `chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49` `[UNKNOWN: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49]` | **`UNKNOWN`** `[UNKNOWN]` | File deletion wrapper; address and ABI completely unverified in tracked files. |
| `DeleteDirectory_Fut` | `UNKNOWN` | None; no stub in `chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49` `[UNKNOWN: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49]` | **`UNKNOWN`** `[UNKNOWN]` | Directory deletion wrapper; address and ABI completely unverified in tracked files. |
| `OpenFastDir` | `UNKNOWN` | None; no stub in `chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49` `[UNKNOWN: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49]` | **`UNKNOWN`** `[UNKNOWN]` | Fast directory open; address and ABI completely unverified in tracked files. |
| `ReadFastDir` | `UNKNOWN` | None; no stub in `chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49` `[UNKNOWN: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49]` | **`UNKNOWN`** `[UNKNOWN]` | Fast directory read; address and ABI completely unverified in tracked files. |
| `closedir` | `UNKNOWN` | None; no stub in `chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49` `[UNKNOWN: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49]` | **`UNKNOWN`** `[UNKNOWN]` | Directory close; address and ABI completely unverified in tracked files. |
| `fileio_semaphore` | `UNKNOWN` | None; no stub in `chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49` `[UNKNOWN: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49]` | **`UNKNOWN`** `[UNKNOWN]` | Mutex semaphore address; unverified in tracked files. |
| `file_counter_var` | `UNKNOWN` | None; no stub in `chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49` `[UNKNOWN: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49]` | **`UNKNOWN`** `[UNKNOWN]` | File counter address; unverified in tracked files. |
| `task_FileWrite` | `UNKNOWN` | None; no stub in `chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49` `[UNKNOWN: chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49]` | **`UNKNOWN`** `[UNKNOWN]` | Asynchronous write task; unverified in tracked files. |

### b.2 The Filesystem-Ready Point & `InitFileModules` Lifecycle Gate

The lifecycle boundary for file operations is governed by the PORT-9A Interface I2 `InitFileModules` readiness gate and the 6-stage lifecycle model in `tools/port9a_runtime_lifecycle.py`:

1. **Static Task Identity & Entry**:
   - The task name string `"InitFileModules"` is verified at ROM `0xFC0BD1AC` (`docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:79; docs/PORT11A_GM110C_ROM_EVIDENCE.md:236`) `[VERIFIED: docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:79; docs/PORT11A_GM110C_ROM_EVIDENCE.md:236]`.
   - Creator function `sub_fc0bd0b4` (`0xFC0BD0B4..0xFC0BD0DB`) creates `"InitFileModules"` with priority `0x19`, stack size `0x1000`, and entry point `0xFC0BD071` (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 208-225; tools/port13_u2_obligations.py:304, 611`) `[VERIFIED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 208-225; tools/port13_u2_obligations.py:304, 611]`.
   - The Thumb entry address is **`0xFC0BD071`** (instruction address `0xFC0BD070`, `push {r4, r5, r6, lr}`) (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 244, 389; tools/port13_u2_obligations.py:302-303, 620`) `[VERIFIED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 244, 389; tools/port13_u2_obligations.py:302-303, 620]`.
   - The historical candidate `0xFC0BD049` is **CONTRADICTED** (`0xFC0BD048` holds literal word `0xFC66BBB0`) (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 388`) `[VERIFIED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 388]`.

2. **Internal Control Flow & Callee Semantics**:
   - Inside `task_InitFileModules` (`0xFC0BD070..0xFC0BD09B`), the first callee is `sub_fc0d9ccc` at `0xFC0BD072` (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:66, 252; tools/port13_u2_obligations.py:309-310`) `[VERIFIED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:66, 252; tools/port13_u2_obligations.py:309-310]`.
   - Inspection of Slice S2B (`0xFC0D9CCC..0xFC0D9CF5`) establishes that `sub_fc0d9ccc` contains zero conditional branches and unconditionally ends with `movs r0, #0; pop {r4, pc}`. Therefore, `r0 = 0` (`r4 == 0`) is constant on normal return and provides **zero dynamic discrimination** of SD card mount state (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 288, 390, 406`) `[VERIFIED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 288, 390, 406]`.
   - The second callee is `sub_fc0d9cf6` at `0xFC0BD086` (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:259; tools/port13_u2_obligations.py:314`) `[VERIFIED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:259; tools/port13_u2_obligations.py:314]`.
   - Logical event `0x5006` is dispatched via `0xFC35B93C(0x5006, 0)` at `0xFC0BD082` and `0xFC35B93C(0x5006, 1)` at `0xFC0BD096` (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:258, 265; tools/port13_u2_obligations.py:313, 317`) `[VERIFIED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:258, 265; tools/port13_u2_obligations.py:313, 317]`.

3. **Six-Stage Filesystem Lifecycle Contract**:
   The formal lifecycle model (`tools/port9a_runtime_lifecycle.py:295-306, 767-803`) defines six discrete stages with exact definitions:
   - **Stage 1 (`task_created`)**: "Static creator call-chain proof + runtime observation that CreateTask was invoked for InitFileModules in current boot generation" (`tools/port9a_runtime_lifecycle.py:295`) `[VERIFIED: tools/port9a_runtime_lifecycle.py:295]`.
   - **Stage 2 (`task_started`)**: "Execution witness confirming task_InitFileModules entry ran in current boot generation after scheduler dispatch" (`tools/port9a_runtime_lifecycle.py:297`) `[VERIFIED: tools/port9a_runtime_lifecycle.py:297]`.
   - **Stage 3 (`init_returned_normally`)**: "Completion witness after sub_fc0d9ccc and sub_fc0d9cf6 return in current boot generation (note: sub_fc0d9ccc r0==0 is constant on normal return and does NOT prove mount)" (`tools/port9a_runtime_lifecycle.py:299`) `[VERIFIED: tools/port9a_runtime_lifecycle.py:299]`.
   - **Stage 4 (`mount_observed`)**: "Independent kernel/storage state proof that FAT volume mount succeeded (event 0x5006 alone is insufficient)" (`tools/port9a_runtime_lifecycle.py:301`) `[VERIFIED: tools/port9a_runtime_lifecycle.py:301]`.
   - **Stage 5 (`fs_io_ready`)**: "Verified non-destructive file open/read capability on mounted volume without contention or timeout" (`tools/port9a_runtime_lifecycle.py:303`) `[VERIFIED: tools/port9a_runtime_lifecycle.py:303]`.
   - **Stage 6 (`warm_restart_safe`)**: "Resolution of warm-restart SD host/card state preconditions (P11 SD1stInit predicate, P12 controller reset, P13 card state, P15 IRQ state) for current boot generation" (`tools/port9a_runtime_lifecycle.py:305`) `[VERIFIED: tools/port9a_runtime_lifecycle.py:305]`.

4. **Crucial Lifecycle Contract Rules & Gate Transition to READY**:
   - `FS_IO_READY` (Stage 5) requires verified non-destructive file open/read capability on the mounted volume without contention or timeout (`tools/port9a_runtime_lifecycle.py:302-303`). It does NOT mean confirmed open/write/close or unmount/flush capability `[VERIFIED: tools/port9a_runtime_lifecycle.py:302-305]`.
   - The modelled gate does NOT become `READY` at Stage 5 (`fs_io_ready`). The gate transitions to `GateState.READY` ONLY at Stage 6 (`warm_restart_safe`), via `record_warm_restart_storage_safety` (`tools/port9a_runtime_lifecycle.py:767-803`), after resolving all four warm-restart SD host/card state preconditions (P11 SD1stInit predicate, P12 controller reset, P13 card state, P15 IRQ state) `[VERIFIED: tools/port9a_runtime_lifecycle.py:767-803]`.
   - Event `0x5006` is rejected as proof of filesystem I/O readiness (`tools/port9a_runtime_lifecycle.py:17-18`) `[VERIFIED: tools/port9a_runtime_lifecycle.py:17-18]`.
   - Write capability for writing runtime telemetry log files (such as `TRACE.LOG`) to SD storage is NOT established by `FS_IO_READY` or `GateState.READY` and remains strictly **`UNKNOWN`** `[UNKNOWN: tools/port9a_runtime_lifecycle.py:302-305; docs/PORT16_FIRSTBOOT_U_TRIAGE.md:518, 538-539]` pending empirical verification or tracked proof of non-destructive write/flush safety.

5. **First-Boot Triage vs Post-First-Boot Telemetry**:
   - In PORT-16 triage (`docs/PORT16_FIRSTBOOT_U_TRIAGE.md:131, 509-518, 537-539`), `U2(a)` (CHDK readiness gate `OBLIG-U2-06/07`), `U2(b)` (deferred CHDK filesystem assertions `OBLIG-U2-04/05`), and `U2(d)-CHDK` (CHDK SpyTask gate consumption) were triaged as `NOT_NEEDED_FOR_FIRST_BOOT` because first boot writes `boot_witness` directly to DRAM and keeps SpyTask disabled (`docs/PORT16_FIRSTBOOT_U_TRIAGE.md:131, 511-513`) `[VERIFIED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:131, 511-513]`.
   - However, for runtime trace flushing and log writing, dynamic filesystem mount readiness and safe file write timing remain **`UNKNOWN`** pending physical runtime observation (`docs/PORT16_FIRSTBOOT_U_TRIAGE.md:518, 538-539; tools/port13_u2_obligations.py:652-730`) `[UNKNOWN: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:518, 538-539]`.

---

## Section (c): LED Control Routes

### c.1 Route 1: High-Level Firmware Function `LEDDrive` — Address UNKNOWN

- **Code Invocation**: `LEDDrive` is called in tracked platform source `vendor/g3x-platform/platform/g3x/lib.c:52-58`:
  ```c
  void camera_set_led(int led, int state, int bright)
  {
      (void)bright;
      extern int _LEDDrive(int, int);
      static char led_table[2] = { 0, 4 };
      _LEDDrive(led_table[led % sizeof(led_table)], state <= 1 ? !state : state);
  }
  ```
  `[VERIFIED: vendor/g3x-platform/platform/g3x/lib.c:52-58]`
- **Firmware ROM Address Status**:
  - No Git-tracked file in the repository establishes any address for `LEDDrive` on GM1.10C.
  - The tracked platform source only declares `extern int _LEDDrive(int, int);` (`vendor/g3x-platform/platform/g3x/lib.c:55`), and the only tracked stubs file defines no `LEDDrive` stub (`chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49`) `[VERIFIED: vendor/g3x-platform/platform/g3x/lib.c:55; chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49]`.
  - Therefore, the GM1.10C firmware address for `LEDDrive` is strictly **`UNKNOWN`** `[UNKNOWN: vendor/g3x-platform/platform/g3x/lib.c:55; chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49]` (`Q-P17-08`).
- **Calling Parameters & Polarity**:
  - The `{0, 4}` index mapping and polarity expression (`state <= 1 ? !state : state`) in `vendor/g3x-platform/platform/g3x/lib.c:56-57` carry no tracked provenance or GM1.10C verification `[UNKNOWN: vendor/g3x-platform/platform/g3x/lib.c:56-57]` (`Q-P17-03`).
  - Whether `LEDDrive` can be safely invoked during early bootloader execution before DryOS device drivers initialize is **`UNKNOWN`**; its address is unknown (above), so its dependencies cannot be checked `[UNKNOWN: vendor/g3x-platform/platform/g3x/lib.c:55]` (`Q-P17-03`).

### c.2 Route 2: Stock Firmware `LEDDrv.c` API (`0xFC12D724`) — Fatal Pre-Kernel

- **Entry Point & Tracked Evidence**: Stock `LEDDrv.c` is documented in `docs/HANDOFF.md:509, 543` and `docs/PROJECT_STATE.md:223, 231` at `0xFC12D724` `[VERIFIED: docs/HANDOFF.md:509, 543; docs/PROJECT_STATE.md:223, 231]`.
- **Pre-Condition Assertion**: `LEDDrv.c` relies on runtime state structures in Low RAM (`0x00009BA4`) initialized late in DryOS boot (`docs/HANDOFF.md:543; docs/PROJECT_STATE.md:231`) `[VERIFIED: docs/HANDOFF.md:543; docs/PROJECT_STATE.md:231]`. Which routine initializes `0x00009BA4` is **`UNKNOWN`**: `sub_fc0bb76e` appears in tracked files only as one call in the startup continuation (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:421`) and as a stub (`chdk-port/platform/g3x/sub/110c/stubs_prototype.S:41`), with no tracked statement of what it initializes `[UNKNOWN: chdk-port/platform/g3x/sub/110c/boot_prototype.c:421; chdk-port/platform/g3x/sub/110c/stubs_prototype.S:41]` (`Q-P17-09`).
- **Pre-Kernel Hazard**: When called from the bootloader or pre-kernel core, `*0x00009BA4 == 0`, triggering an unconditional kernel panic and system crash (`docs/HANDOFF.md:509; docs/PROJECT_STATE.md:223`) `[VERIFIED: docs/HANDOFF.md:509; docs/PROJECT_STATE.md:223]`.
- **Conclusion**: `LEDDrv.c` is **REJECTED (FATAL PRE-KERNEL)** for early boot telemetry `[VERIFIED: docs/HANDOFF.md:509; docs/PROJECT_STATE.md:223]`.

### c.3 Route 3: Direct MMIO GPIO Registers — Hazardous & Unverified

- **Evaluated MMIO Addresses**:
  - `0xD20B0884` and `0xD20B0810` (historical forum proposals for rear green LED).
  - `0xD20B0994` (G5X MMIO GPIO register, explicitly rejected for G3X in `vendor/g3x-platform/platform/g3x/lib.c:45-46`: `// NOTE: G3X GPIO LED MMIO address is UNVERIFIED. // DO NOT copy G5X MMIO (0xd20b0994). Left inert.`) `[VERIFIED: vendor/g3x-platform/platform/g3x/lib.c:45-46]`.
- **Absence as a ROM literal**: Neither `0xD20B0884` nor `0xD20B0810` exists anywhere as a literal in GM1.10C firmware (`docs/HANDOFF.md:509, 542; docs/PROJECT_STATE.md:223, 231`) `[VERIFIED: docs/HANDOFF.md:509, 542; docs/PROJECT_STATE.md:223, 231]`. This shows only that the addresses are not stored as literal words; firmware may compute MMIO addresses at runtime (base + offset), so literal absence does not show that no GPIO LED route exists `[INFERRED: docs/RESTART_SD_HOST_AUDIT.md:25]` (that line records SD-host register addresses computed as `table[host] + off − 0x38000000`, an example of runtime address computation in this firmware).
- **Hardware Hazard**: Tracked docs state that the `0xD20B0000` MMIO range controls motor coils and power rails (and the SPI bus), and that blind writes risk hardware damage (`docs/HANDOFF.md:509, 542; docs/PROJECT_STATE.md:223, 231`) `[VERIFIED: docs/HANDOFF.md:509, 542; docs/PROJECT_STATE.md:223, 231]`.
- **Current Port Status**: In `vendor/g3x-platform/platform/g3x/lib.c:47-50`, `debug_led(int state)` is intentionally left as an inert stub `(void)state;` because the G3X MMIO GPIO LED register is unverified `[VERIFIED: vendor/g3x-platform/platform/g3x/lib.c:47-50]`.
- **Conclusion**: A direct MMIO GPIO LED register for GM1.10C is **`UNKNOWN`** `[UNKNOWN: vendor/g3x-platform/platform/g3x/lib.c:45-50; docs/HANDOFF.md:509]`. Missing evidence: a tracked ROM caller chain from an LED driver (`LEDDrv.c` at `0xFC12D724` or `LEDDrive`) down to the register store, showing the computed address, bit and polarity; no tracked document contains that trace (`Q-P17-06`).

---

## 2. Minimal Proposed ROM Ranges (for non-VERIFIED Items)

In accordance with strict project rules:
- Zero ROM bytes were read or committed in this task.
- Each proposed range is at most 512 bytes, and the total footprint across all ranges is at most 4 KiB.
- Each proposed range has an exact start address, byte length, specific technical reason, and an exact justifying citation from Git-tracked repository evidence.
- Every proposed start address is subjected to an explicit Thumb-bit derivation: `(tracked_citation_addr) & ~1 = start_addr`.
- Any item whose start address cannot be justified from tracked evidence (such as `LEDDrive` or low-level `Open`/`Write`/`Close`), or that is a runtime/hardware property, is classified as `UNKNOWN: not closable from static ROM ranges within budget` in the closure inventory below.
- Range IDs keep the numbering of the previous revision; retired IDs are noted, not reused.

### Closure Inventory (every non-VERIFIED item in sections (a)-(c))

| # | Item (section) | Label | Disposition | Q-P17 ID |
|---|---|:---:|---|:---:|
| 1 | `.bss` ordering, `ALIGN (0x10)` before `_end`, `_end`/`link_bss_end` clauses of the linker script (a.1) | `UNKNOWN` (script untracked) | **UNKNOWN: not closable from static ROM ranges within budget.** It is a property of the untracked host file `chdk-port/tools/link-boot.ld`, not of ROM; it closes only if that script (or a quote of its `.bss` clause) becomes tracked. | `Q-P17-10` |
| 2 | 12-byte pre-`_end` fill and the $S \le 12$ placement rule (a.2, a.3) | `INFERRED` (local map only) | **UNKNOWN: not closable from static ROM ranges within budget.** Build-specific host link output; depends on item 1. | `Q-P17-10` |
| 3 | Whether a $S > 4$ trace ring with `_end` growth is safe for DryOS heap at runtime (a.3 item 4) | `UNKNOWN` | **UNKNOWN: not closable from static ROM ranges within budget.** Runtime heap demand is not a static ROM property; only the static headroom check exists (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:179-186`). | `Q-P17-01` |
| 4 | Trace ring survival across a soft restart (a.4) | `UNKNOWN` | **UNKNOWN: not closable from static ROM ranges within budget.** DRAM retention is a hardware/runtime property. Canon's restart routine is identified at `0xFC0D03E8` (code VERIFIED, jump reachability UNKNOWN: `docs/PORT3A_RESTART_IRQ_AUDIT.md:33`; `docs/PROJECT_STATE.md:150`), but no tracked line addresses DRAM retention, so no ROM range is proposed for it. | `Q-P17-02` |
| 5 | GM1.10C ROM BSS zeroing-loop start (`0xFC020068` vs `0xFC020070`) (a.4) | `UNKNOWN` | **Range R-P17-09.** | `Q-P17-12` |
| 6 | `Fopen_Fut` / `Fclose_Fut` / `Fread_Fut` / `Fwrite_Fut` register ABI and error returns (b.1) | `UNKNOWN` (shape `INFERRED`) | **Range R-P17-02.** | `Q-P17-11` |
| 7 | `Feof_Fut` / `Fflush_Fut` ABI and semantics (b.1) | `UNKNOWN` | **Range R-P17-02** (same slice; `0xFC37F110` and `0xFC37F138` lie inside it). | `Q-P17-11` |
| 8 | `GetDrive_TotalClusters` ABI, drive-number encoding and return layout (b.1) | `UNKNOWN` | **Range R-P17-07.** | `Q-P17-11` |
| 9 | Loader `open` / `read` / `close` helper ABI (b.1) | `UNKNOWN` | **Range R-P17-08.** | `Q-P17-11` |
| 10 | Low-level `Open`/`Close`/`Write`/`Read`, POSIX `open`/`close`, `Fseek_Fut`, `Fgets_Fut`, directory and delete wrappers, `task_FileWrite` addresses (b.1) | `UNKNOWN` | **UNKNOWN: not closable from static ROM ranges within budget.** No tracked start address exists (`chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49`); finding them needs an unbounded ROM search. (Former R-P17-04.) | `Q-P17-07` |
| 11 | `fileio_semaphore` / `file_counter_var` RAM addresses (a.5, b.1) | `UNKNOWN` | **UNKNOWN: not closable from static ROM ranges within budget.** No tracked anchor address; depends on item 10. | `Q-P17-07` |
| 12 | `[0xFC0D9D54]` literal loaded by `sub_fc0d9cf6` (b.2) | `UNKNOWN` | **Range R-P17-03.** | `Q-P17-04` |
| 13 | FAT mount observed / `fs_io_ready` / safe write timing for `TRACE.LOG` (b.2 items 4-5) | `UNKNOWN` | **UNKNOWN: not closable from static ROM ranges within budget.** Lifecycle Stages 4-5 require runtime proof by definition (`tools/port9a_runtime_lifecycle.py:301, 303`); R-P17-03 only narrows the static code path. | `Q-P17-04` |
| 14 | `LEDDrive` ROM address (c.1) | `UNKNOWN` | **UNKNOWN: not closable from static ROM ranges within budget.** No tracked start address (`vendor/g3x-platform/platform/g3x/lib.c:55`; `chdk-port/platform/g3x/sub/110c/stubs_prototype.S:9-49`). (Former R-P17-01.) | `Q-P17-08` |
| 15 | `LEDDrive` ID mapping `{0, 4}`, polarity, pre-kernel safety (c.1) | `UNKNOWN` | **UNKNOWN: not closable from static ROM ranges within budget.** Depends on item 14. | `Q-P17-03` |
| 16 | Routine that initializes `0x00009BA4` (role of `sub_fc0bb76e` unknown) (c.2) | `UNKNOWN` | **UNKNOWN: not closable from static ROM ranges within budget.** Finding the writer of `0x00009BA4` needs a whole-ROM reference search; no tracked start address bounds it. | `Q-P17-09` |
| 17 | GPIO/MMIO LED register route (c.3) | `UNKNOWN` | **UNKNOWN: not closable from static ROM ranges within budget.** Tracked docs show only that `0xD20B0884`/`0xD20B0810` are not stored as literals (`docs/HANDOFF.md:509, 542`) and that the G3X GPIO LED address is unverified (`vendor/g3x-platform/platform/g3x/lib.c:45-46`). The address may be computed at runtime; recovering it needs a traced call chain from an LED driver to the register store, whose length no tracked evidence bounds. (Former R-P17-05.) | `Q-P17-06` |
| 18 | `0x40000000` uncached mirror; `0x006F0000` ARAM upper bound (a.5) | `INFERRED` | **UNKNOWN: not closable from static ROM ranges within budget.** Background only; not needed by this task. | — |
| 19 | Tracing-OFF layout leaves `boot_witness`/`_end` unchanged (a.3 item 3) | `INFERRED` | **UNKNOWN: not closable from static ROM ranges within budget.** Host link property; closed by the OFF-layout check in `p17-trace-core`. | `Q-P17-01` |
| 20 | FW/HW rows of a.5 for GM1.10C: ROM BSS bounds `0x0003F4F4`/`0x003489B4` (`docs/PORT14_Q_MEM03_BSS.md:270-271`), default DryOS heap base and pool bounds `0x00600014`/`0x0060E000`, ROM headroom check at `0x006CE000` (`docs/PORT13_MEMORY_OBLIGATIONS.md:76-79`), vectors at `0x00000000`, low-RAM start `0x00008000`, role of `0x00008074..0x0000807C` | `INFERRED` | Tracked anchors exist for the static memory items. `docs/PORT13_MEMORY_OBLIGATIONS.md:79` (`OBLIG-MEM-08`, status `INFERRED`) reads "DryOS System Headroom Comparator Limit (`0x006CE000 - r4 >= 0x000B1FEC`, `0xFC05B3C8`)". `docs/PROJECT_STATE.md:304` reads "Proved that `0xFC05B3C8` is the sole routine establishing the system heap base via literal `0x003489B4` (`0xFC05B450`). The 0x78-byte setup structure on stack passes heap limit `0x0060E000` (`sp[0]`), heap base `0x003489B4` (`sp[2]`), and usable heap size `0x00600014 - r4` (`sp[3]`)". `docs/PORT14_Q_MEM03_BSS.md:287` reads "`0xFC0200DC` (reported as the ROM literal for BSS zero end `0x003489B4`) and `0xFC05B450` (reported as the ROM literal for DryOS heap base `0x003489B4` in `0xFC05B3C8`) appear **only** in high-level narrative project summaries", and `docs/PORT13_MEMORY_OBLIGATIONS.md:74` (`OBLIG-MEM-03`) lists "literals `0xFC0200DC`, `0xFC05B450`".<br>**BSS bounds**: loop instructions in **Range R-P17-09**; the upper-bound literal `0xFC0200DC` in **Range R-P17-11**. No tracked line gives the address of the lower-bound (`0x0003F4F4`) literal, so that bound stays `INFERRED` even after both ranges are read.<br>**Default heap base, pool bounds `0x00600014`/`0x0060E000`, headroom check `0x006CE000`**: **Range R-P17-10** (routine `0xFC05B3C8` through the heap-base literal at `0xFC05B450`). Any other literal of that routine past `0xFC05B453` stays outside the range; such values stay `INFERRED`.<br>**Vectors at `0x00000000`, low-RAM start `0x00008000`, role of `0x00008074..0x0000807C`**: none of the three anchor lines above names them; **deferred beyond PORT-17 scope**, no range proposed (the only tracked ROM anchors are the prototype comment at `chdk-port/platform/g3x/sub/110c/boot_prototype.c:93-94` and the already ROM-verified literal at `docs/PORT5D_EARLY_BOOT_ROM_VERIFICATION.md:36`).<br>All rows stay `INFERRED` until the ranges are inspected. | `Q-P17-12`, `Q-P17-13` |
| 21 | Physical DRAM size / upper boundary (a.5) | `UNKNOWN` | **UNKNOWN: not closable from static ROM ranges within budget.** Hardware property; `MAXRAMADDR` (`tools/build_candidate_port2a.py:200`) is a build define only (`docs/RESEARCH_LOG.md:99`; `docs/PORT13_REVIEW_PR23.md:87`). | `Q-P17-13` |

Former R-P17-06 (soft-restart retention) is now inventory item 4.

### Proposed ROM Ranges Table

| ID | Target Item | Start Address | Length | Tracked Justifying Citation & Thumb-Bit Derivation | Technical Reason for Proposed Slice | Status |
|---|---|:---:|:---:|---|---|:---:|
| **R-P17-02** | `Fut` stream wrappers: `Fopen_Fut`, `Fclose_Fut`, `Fread_Fut`, `Fwrite_Fut`, `Feof_Fut`, `Fflush_Fut` (items 6-7) | `0xFC37EFA6` | 512 B (`0xFC37EFA6..0xFC37F1A5`) | **Citation**: `docs/HANDOFF.md:1025` (`Fopen_Fut` `0xFC37EFA7`, `Fclose_Fut` `0xFC37EFCF`, `Fread_Fut` `0xFC37F041`, `Fwrite_Fut` `0xFC37F077`); `docs/HANDOFF.md:1026` (`Feof_Fut` `0xFC37F111`, `Fflush_Fut` `0xFC37F139`).<br>**Thumb check**: `0xFC37EFA7 & ~1 = 0xFC37EFA6`; the other five starts (`0xFC37EFCE`, `0xFC37F040`, `0xFC37F076`, `0xFC37F110`, `0xFC37F138`) lie inside the range. | Read the six wrapper prologues and bodies to fix register ABI, return/error convention and EOF/flush semantics. The first five bodies are bounded by the next documented start; `Fflush_Fut` gets `0x6E` (110) bytes, and its body or literal pool may extend past `0xFC37F1A5` (then `UNKNOWN` remains). | `PROPOSED` |
| **R-P17-03** | 32-bit literal `[0xFC0D9D54]` loaded by `sub_fc0d9cf6` at `0xFC0D9D02` (item 12) | `0xFC0D9D54` | 4 B (`0xFC0D9D54..0xFC0D9D57`) | **Citation**: `docs/PORT11A_GM110C_ROM_EVIDENCE.md:90` (target of `0xFC0D9D02: ldr r4, [pc, #0x50]`, occupying `0x0D9D54..0x0D9D57`, "not read"); also `docs/PORT11A_GM110C_ROM_EVIDENCE.md:286`.<br>**Alignment check**: data word, 4-byte aligned; no Thumb bit applies. | The body of `sub_fc0d9cf6` is already documented (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:285-286`); only this literal is missing. Its value says what `r4` points to (for example a mount-state structure) before the calls to `0xFC37AD52`/`0xFC0F9BA4`. Replaces the previous 96-byte range at `0xFC0D9CF6`, which stopped at `0xFC0D9D55` and missed bytes `0xFC0D9D56..57`. | `PROPOSED` |
| **R-P17-07** | `GetDrive_TotalClusters` (item 8) | `0xFC37AF8A` | 128 B (`0xFC37AF8A..0xFC37B009`) | **Citation**: `docs/HANDOFF.md:1026` (`GetDrive_TotalClusters` `0xFC37AF8B`).<br>**Thumb check**: `0xFC37AF8B & ~1 = 0xFC37AF8A`. | Read the prologue, argument use and return path to fix drive-number encoding and return layout. Function length is not documented; if the body exceeds 128 B the remainder stays `UNKNOWN`. | `PROPOSED` |
| **R-P17-08** | Loader `open` / `close` / `read` helpers used by `StartDiskboot` (item 9) | `0xFC37B4AE` | 256 B (`0xFC37B4AE..0xFC37B5AD`) | **Citation**: `docs/RESTART_SD_HOST_AUDIT.md:14` (open `0xFC37B4AE`, close `0xFC37B4B0`, read `0xFC37B552`, all `bl` targets).<br>**Thumb check**: even instruction addresses; `& ~1` leaves them unchanged. | Covers the open entry, the close entry 2 bytes later, and the read entry plus `0x5C` (92) bytes of its body, to fix argument registers and return convention. The read body may extend past `0xFC37B5AD` (then `UNKNOWN` remains). | `PROPOSED` |
| **R-P17-09** | GM1.10C ROM BSS zeroing loop (item 5) | `0xFC020068` | 20 B (`0xFC020068..0xFC02007B`) | **Citation**: `docs/PORT3A_RESTART_IRQ_AUDIT.md:20` ("zero loop at `0xFC020068..78`"); competing start `0xFC020070` per `docs/PORT14_Q_MEM03_BSS.md:280`.<br>**Thumb check**: even instruction address. | Covers both candidate starts and the last instruction at `0xFC020078` (Thumb, up to 4 bytes) to decide which start is correct (`docs/PORT14_Q_MEM03_BSS.md:282`). Any PC-relative literal the loop loads lies outside this range; the upper-bound literal is covered by R-P17-11. | `PROPOSED` |
| **R-P17-10** | DryOS heap setup routine `0xFC05B3C8` and its heap-base literal (item 20) | `0xFC05B3C8` | 140 B (`0xFC05B3C8..0xFC05B453`) | **Citation**: `docs/PORT13_MEMORY_OBLIGATIONS.md:79` ("`0x006CE000 - r4 >= 0x000B1FEC`, `0xFC05B3C8`"); `docs/PROJECT_STATE.md:304` ("`0xFC05B3C8` is the sole routine establishing the system heap base via literal `0x003489B4` (`0xFC05B450`)"); `docs/PORT14_Q_MEM03_BSS.md:287`.<br>**Alignment check**: start taken as written in the cited lines (even, no Thumb bit); the literal word at `0xFC05B450` is 4-byte aligned and its last byte is `0xFC05B453`. | Smallest window from the cited routine start through the end of the cited literal word. Confirms the heap-base literal and whether the headroom compare and the `0x0060E000`/`0x00600014` descriptor stores lie in this window. Literals of the routine beyond `0xFC05B453` are not proposed (then `INFERRED` remains for those values). | `PROPOSED` |
| **R-P17-11** | 32-bit ROM literal for the BSS zero end `0x003489B4` (item 20) | `0xFC0200DC` | 4 B (`0xFC0200DC..0xFC0200DF`) | **Citation**: `docs/PORT14_Q_MEM03_BSS.md:287` ("`0xFC0200DC` (reported as the ROM literal for BSS zero end `0x003489B4`)"); `docs/PORT13_MEMORY_OBLIGATIONS.md:74` ("literals `0xFC0200DC`, `0xFC05B450`").<br>**Alignment check**: data word, 4-byte aligned; no Thumb bit applies. | Confirms the upper bound used by the GM1.10C ROM BSS zeroing loop (R-P17-09). | `PROPOSED` |

Retired IDs: R-P17-01 (`LEDDrive`), R-P17-04 (low-level file primitives), R-P17-05 (GPIO LED register) and R-P17-06 (soft-restart retention) carry no range; see closure inventory items 14, 10, 17 and 4.

### Total Proposed ROM Range Footprint
- **Per-range lengths**: R-P17-02 = 512 B, R-P17-03 = 4 B, R-P17-07 = 128 B, R-P17-08 = 256 B, R-P17-09 = 20 B, R-P17-10 = 140 B, R-P17-11 = 4 B. Each is $\le 512$ B.
- **Total Footprint**: $512 + 4 + 128 + 256 + 20 + 140 + 4 = \mathbf{1064}$ **bytes**, within the 4,096-byte ceiling. The trace ranges for (b) file stubs / FS-ready (R-P17-02, R-P17-03, R-P17-07, R-P17-08) are all kept; (c) LED has no tracked anchor and so no range (items 14-17).
- No two ranges overlap.

---

## 3. Open Questions (Q-P17-*)

The following open questions are codified for subsequent implementation tasks and code TODOs:

- **`Q-P17-01` (Trace Ring Linker Placement & Section Mechanics)**:  
  Can a conditionally compiled `.g3x_trace` section (0 bytes when tracing is OFF; e.g. 4096 bytes when tracing is ON) sit between `.data` and `.bss` without displacing `boot_witness` at `0x0035F7A0`, and does the resulting downstream displacement of `_end` (`0x00366CB0`) and `new_sa` safely preserve the required DryOS heap headroom ($S \le \text{remaining} - \text{required} = 0x00367350 - 0x000B1FEC = 0x002B5364$)? The headroom figures come from prototype source constants (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:180-181`); that GM1.10C ROM uses the same check is INFERRED (`docs/PORT13_MEMORY_OBLIGATIONS.md:79`).  
  *OFF-layout check (done in task `p17-trace-core`)*: the claim that tracing OFF leaves `boot_witness = 0x0035F7A0` and `_end = 0x00366CB0` unchanged is only INFERRED (a.3 item 3). `p17-trace-core` must (1) leave out the whole `.g3x_trace` stanza when `G3X_TRACE` is OFF, including any `ALIGN`, location-counter assignment, `KEEP` and reference symbols (preprocessor or an ON-only linker fragment); (2) compare `boot_witness` and `_end` in the OFF link map with `docs/PORT16_WITNESS_ADDRESS.md:15, 218` and `docs/PORT16_CANDIDATE_BUILD.md:247, 250`; and (3) pass `candidate_validate` (`docs/PORT16_CANDIDATE_BUILD.md:22, 150, 183`). Until then this item stays INFERRED.

- **`Q-P17-02` (DRAM Soft-Restart Retention & Restart Jump Reachability)**:  
  Does volatile system DRAM in the relocated core space (`0x003489B4..0x00366CB0`) retain its contents across a Canon soft/warm restart, or does the hardware memory controller reset and re-initialize DRAM banks, destroying pre-restart trace data? Canon's restart routine is identified at `0xFC0D03E8` (`docs/PORT3A_RESTART_IRQ_AUDIT.md:33`; `docs/PROJECT_STATE.md:150`); which caller and mode, if any, reach its `bx 0xFC020001` is `UNKNOWN`.  
  *(Note on Question Scope Refinement & ID Stability: earlier drafts conflated `sub_fc05c4e0` with a restart routine; `chdk-port/platform/g3x/sub/110c/boot_prototype.c:391-397` and `docs/RESTART_SD_HOST_AUDIT.md:119-124` identify `sub_fc05c4e0` as the predicate gating `SD1stInit` task creation (`sub_fc05c4e0(0)` bit 0 == 0). Canon's restart routine is `0xFC0D03E8` (`docs/PORT3A_RESTART_IRQ_AUDIT.md:33`; `docs/PROJECT_STATE.md:150`); only the CHDK `Restart` stub binding is still a `NULL_SUB` (`docs/HANDOFF.md:979`).)*

- **`Q-P17-03` (`LEDDrive` Calling Contract & Pre-Kernel Safety)**:  
  What are the valid integer LED IDs for `LEDDrive` on GM1.10C (specifically mapping the AF-assist lamp and top power LED), what is their active polarity, and does `LEDDrive` depend on any pre-kernel device driver state that would trigger an unhandled fault if called during bootloader execution?

- **`Q-P17-04` (Filesystem Mount Verification Point)**:  
  What specific ROM routine or completion flag establishes that the SD card FAT filesystem has transitioned from Stage 3 (`init_returned_normally`) to Stage 4 (`mount_observed`) and Stage 5 (`fs_io_ready`) per `tools/port9a_runtime_lifecycle.py:295-306`, enabling non-corrupting file writes?

- **`Q-P17-05` (Telemetry File API Selection)**:  
  For post-first-boot trace logging, should the port utilize high-level stream file wrappers (`Fopen_Fut` `0xFC37EFA7`, `Fwrite_Fut` `0xFC37F077`, `Fclose_Fut` `0xFC37EFCF`) or low-level POSIX/DryOS primitives, and what DryOS task context or priority is required to avoid deadlocking with storage controller semaphores?

- **`Q-P17-06` (Direct Hardware MMIO GPIO LED Route)**:  
  Does GM1.10C feature a safe MMIO GPIO register for driving an LED without executing firmware code, or is `LEDDrive` the sole viable LED control route for the G3 X?

- **`Q-P17-07` (Low-Level File I/O Primitives & Semaphore Recovery)**:  
  What are the verified GM1.10C ROM entry addresses for low-level DryOS file descriptor routines (`Open`, `Close`, `Write`), does GM1.10C utilize a filesystem mutex semaphore (CHDK symbol `fileio_semaphore`), and what is its verified RAM address?

- **`Q-P17-08` (`LEDDrive` Firmware Address Recovery)**:  
  What is the verified GM1.10C ROM entry address for `LEDDrive` (called via `_LEDDrive` in `vendor/g3x-platform/platform/g3x/lib.c:55-57`), and can it be recovered via safe static disassembly of Canon Basic event procedure registration tables or UI task handlers?

- **`Q-P17-09` (`LEDDrv` State Initializer)**:  
  Which GM1.10C routine writes the `LEDDrv` state word at `0x00009BA4` (`docs/HANDOFF.md:509, 543`), and at which startup step does it run? The role of `sub_fc0bb76e` (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:421`) is not established by any tracked line.

- **`Q-P17-10` (Linker Script Provenance)**:  
  Should `chdk-port/tools/link-boot.ld` (or a verbatim quote of its `.bss`, `_end` and `link_bss_end` clauses) become tracked, so that the `ALIGN (0x10)` before `_end` and the 12-byte pre-`_end` fill seen only in the local map can be cited instead of inferred?

- **`Q-P17-11` (File Wrapper ABI)**:  
  What are the register ABI, return values and error conventions of `Fopen_Fut`, `Fclose_Fut`, `Fread_Fut`, `Fwrite_Fut`, `Feof_Fut`, `Fflush_Fut` (`docs/HANDOFF.md:1025-1026`), `GetDrive_TotalClusters` (`docs/HANDOFF.md:1026`) and the `StartDiskboot` loader `open`/`read`/`close` helpers (`docs/RESTART_SD_HOST_AUDIT.md:14`)? Ranges R-P17-02, R-P17-07 and R-P17-08.

- **`Q-P17-12` (ROM BSS Zeroing Loop Start)**:  
  Does the GM1.10C BSS zeroing loop start at `0xFC020068` (`docs/PORT3A_RESTART_IRQ_AUDIT.md:20`) or `0xFC020070` (`docs/PORT14_Q_MEM03_BSS.md:280`)? Range R-P17-09. Does the upper-bound literal at `0xFC0200DC` (`docs/PORT14_Q_MEM03_BSS.md:287`) hold `0x003489B4`? Range R-P17-11. Its bounds `0x0003F4F4..0x003489B4` on GM1.10C ROM stay `INFERRED` (`docs/PORT14_Q_MEM03_BSS.md:270-271`) until these ranges are read; the lower-bound literal has no tracked address.

- **`Q-P17-13` (Build Configuration vs GM1.10C Memory Facts)**:  
  Which a.5 values that are VERIFIED only as prototype/build configuration also hold on GM1.10C firmware and hardware: DryOS pool bounds `0x00600014`/`0x0060E000` and the `0x006CE000` headroom check (`docs/PORT13_MEMORY_OBLIGATIONS.md:76-79`, all `INFERRED`; routine `0xFC05B3C8` and heap-base literal `0xFC05B450` per `docs/PROJECT_STATE.md:304`, Range R-P17-10), and the physical DRAM size, which is `UNKNOWN` (`MAXRAMADDR` at `tools/build_candidate_port2a.py:200` is a build define only; `docs/RESEARCH_LOG.md:99`; `docs/PORT13_REVIEW_PR23.md:87`)? Trace-ring code must not rely on any of them as firmware facts.
