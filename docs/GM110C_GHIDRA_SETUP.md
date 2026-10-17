# GM1.10C Ghidra setup and reproducible workflow

Updated: 2026-10-17  
Scope: Phase 3B installed tooling, reproducible import, and targeted static analysis  
Input: local, ignored `firmware/dumps/GM1.10C/PRIMARY.BIN`  
Input SHA-256: `9911855772e433c877a9914f16d3735e15a48ca63352633e8f10364182912578`

## Result

The evidence-supported raw import configuration is Ghidra language `ARM:LE:32:v7`, compiler specification `default`, image base `0xFC000000`, file offset `0`, and length `0x02000000`. The image is mixed-state firmware: the directly decoded trampoline at `0xFC004510` is ARM and deliberately enters Thumb state. This does not justify ARM disassembly across the rest of the image or make every odd ROM pointer a confirmed function.

The workflow below was executed successfully after the owner completed MacPorts installation. Ghidra 12.1.4 imported the image as raw `ARM:LE:32:v7:default` at `0xFC000000` with length `0x02000000`. Targeted scripts established Thumb context only in bounded windows around evidence-backed odd pointers; the ROM was not linearly disassembled in one mode. The local project is Git-ignored and no proprietary bytes were committed or uploaded.

## 1. Host and compatibility check

| Item | Observed 2026-10-17 | Result |
|---|---|---|
| macOS | 14.8.9, build `23J631`, Darwin 23.6.0 | compatible Darwin host |
| Architecture | `x86_64`; Intel Core i7-9750H | matches Intel Mac target |
| Existing default Java | Temurin OpenJDK `26.0.2.1`, x86_64, `/Library/Java/JavaVirtualMachines/temurin-26.jdk/Contents/Home` | left unchanged |
| MacPorts | `/opt/local/bin/port`, version 2.12.6 | available |
| MacPorts Ghidra | `ghidra @12.1.4_0`, Darwin; depends on `openjdk25-zulu`, Python 3.14 and build tools | package resolves; separate MacPorts JDK avoids replacing the existing default |
| MacPorts Capstone | `capstone @5.0.6_0`, Darwin, no dependencies | package resolves |
| Installed state | Ghidra `12.1.4_0`, Capstone `5.0.6_0`, Zulu JDK `25.0.4.1` active | verified with MacPorts and smoke tests |

MacPorts warned that its port definitions were more than two weeks old. `port selfupdate` was deliberately not run because it updates the broader MacPorts installation and was not necessary to establish package availability. The attempted command was:

```sh
sudo -n port install ghidra capstone
```

The earlier unattended attempt returned `sudo: a password is required`; the owner subsequently completed the installation locally. No password entered the repository or agent logs.

The system default remains Temurin 26. Targeted headless commands set `JAVA_HOME` only for that process to MacPorts Zulu 25; no global Java selection was changed.

## 2. Primary evidence for processor selection

| Claim | Evidence | Confidence / limit |
|---|---|---|
| DIGIC 6/7 raw dumps use ARM v7 little-endian with the default compiler in Ghidra | CHDK Wiki, [Firmware analysis with Ghidra](https://chdk.fandom.com/wiki/Firmware_analysis_with_Ghidra), retrieved 2026-10-17 | **HIGH for CHDK workflow**; not a claim about the exact CPU core |
| Ghidra's language ID is `ARM:LE:32:v7`, described as “Generic ARM/Thumb v7 little endian” | NSA Ghidra [`ARM.ldefs`](https://github.com/NationalSecurityAgency/ghidra/blob/master/Ghidra/Processors/ARM/data/languages/ARM.ldefs), retrieved 2026-10-17 | **HIGH** |
| GM1.10C contains an ARM trampoline that sets bit 0 and branches into Thumb state | local bytes at `0xFC004510`, audited in `GM110C_ROM_ANALYSIS.md` | **HIGH for the sequence**; early-boot role remains **MEDIUM** |
| Image base is `0xFC000000` and size is `0x02000000` | successful dumper log, expected hash/size, internal pointers and `gaonisoy` at `0xFC020004` | **HIGH** |

Do not select an ARM-only language, force Thumb globally, or label `0xFC004510` a reset vector. The first two choices contradict the mixed-state bytes; the third lacks a proven hardware entry chain.

## 3. Tooling gate

On 2026-10-17 MacPorts installed `ghidra @12.1.4`, `capstone @5.0.6`, and `openjdk25-zulu @25.36.205`. Recheck installed state with:

```sh
port info ghidra
port info capstone
```

Installation command completed by the owner:

```sh
sudo port install ghidra capstone
```

MacPorts references: [Ghidra](https://ports.macports.org/port/ghidra/details/) and [Capstone](https://ports.macports.org/port/capstone/details/), retrieved 2026-10-17. The installed Ghidra release's bundled documentation and JDK requirement take precedence over the moving `master` branch.

## 4. Pre-import integrity gate

Run from the repository root. The analyzer opens the ROM read-only and fails on an identity mismatch:

```sh
python3 tools/analyze_rom.py \
  firmware/dumps/GM1.10C/PRIMARY.BIN \
  --base 0xFC000000 \
  --expect-size 0x2000000 \
  --expect-sha256 9911855772e433c877a9914f16d3735e15a48ca63352633e8f10364182912578 \
  > /tmp/g3x-gm110c-analysis.json
```

Create any future Ghidra project only under the already ignored `analysis-workspace/`, for example `analysis-workspace/ghidra/g3x-gm110c`. Never place a project beside the dump, add it to Git, or upload it: a database and decompiler cache are derivative of proprietary firmware.

## 5. Raw import recipe

Executed headless import:

```sh
export JAVA_HOME=/opt/local/Library/Java/JavaVirtualMachines/jdk-25-azul-zulu.jdk/Contents/Home
GHIDRA_HOME=/opt/local/share/java/ghidra-12.1.4
"$GHIDRA_HOME/support/analyzeHeadless" analysis-workspace/ghidra g3x-gm110c-v2 \
  -import firmware/dumps/GM1.10C/PRIMARY.BIN \
  -loader BinaryLoader \
  -loader-baseAddr 0xFC000000 \
  -loader-blockName ROM \
  -loader-fileOffset 0 \
  -loader-length 0x02000000 \
  -processor ARM:LE:32:v7 \
  -cspec default \
  -noanalysis
```

Canonical local project: `analysis-workspace/ghidra/g3x-gm110c-v2`. The earlier `g3x-gm110c` project is a superseded context-range experiment and must not be used as evidence. Both remain ignored.

1. Create a non-shared project under `analysis-workspace/ghidra/`.
2. Import `PRIMARY.BIN` as **Raw Binary**.
3. Select language `ARM:LE:32:v7` and compiler `default`.
4. Set base address `0xFC000000`, file offset `0`, length `0x02000000`.
5. Initially postpone broad auto-analysis. Keep the source block read-only.
6. Label the two header words and the proven trampoline without assigning reset/vector semantics.
7. Set ARM context at `0xFC004510`; follow its `BX` and set Thumb context only on the reached path. For table pointers with bit 0 set, clear bit 0 for the storage address and treat the bit as a Thumb-state indication, pending valid disassembly.
8. Split proven all-`0xFF` intervals from `GM110C_MEMORY_MAP.md` and remove execute permission from them. Do not classify zero-heavy or high-entropy ranges by entropy alone.
9. Seed the directly evidenced event-procedure bindings from `GM110C_FUNCTION_MAP.md`. Preserve each original name and table address as a plate comment.
10. Run analysis incrementally, reviewing conflicts at pointer tables, strings, literal pools, and state transitions before creating more code.

The simplest initial memory model is one loaded read-only ROM block followed by splits for proven fill. RAM, MMIO, copied code, and overlay blocks must wait for GM1.10C-specific copy-loop or reference evidence.

Targeted analysis commands use `tools/ghidra/SeedAndReportHdmi.java` and `ExpandAndReportHdmi.java`. They verify the language/compiler, set `TMode=1` in bounded local windows around already verified odd pointers, create only the seeded functions and followed flows, and write textual reports to `/tmp`. They do not modify the input file.

## 6. CHDK-assisted analysis

Pinned comparison source: CHDK r5491, commit [`21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6`](https://github.com/01luna/CHDK/tree/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6), dated 2020-05-11.

Relevant scripts and sources:

- [`tools/ghidra_scripts/InitCHDKMemMap.py`](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/tools/ghidra_scripts/InitCHDKMemMap.py) creates ROM/RAM mappings from generated stubs and handles copied code/data regions.
- [`tools/ghidra_scripts/ImportCHDKStubs.py`](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/tools/ghidra_scripts/ImportCHDKStubs.py) imports CHDK names and entry points.
- [`tools/ghidra_scripts/CleanThumb2BookmarkErrors.py`](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/tools/ghidra_scripts/CleanThumb2BookmarkErrors.py) addresses known Thumb-2 bookmark noise after review.
- [`tools/finsig_thumb2.c`](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/tools/finsig_thumb2.c) contains the R57-era task and event-procedure signature knowledge.

Safe order after tools are approved:

1. Build reviewed CHDK tools from the pinned tree using its Makefile; never execute a downloaded binary or ad-hoc script.
2. Generate GM1.10C-specific stubs from the local ROM.
3. Review addresses and run `InitCHDKMemMap.py` in its non-mutating/preview mode first.
4. Import generated stubs while excluding copied reference `stubs_min.S` and `stubs_entry_2.S` unless every included value has been independently corrected for GM1.10C. CHDK's own script warns about these files.
5. Use M10 and SX710 as the first R57 Version Tracking references; use G5 X as a structural R58 reference. Never match on address equality.

CHDK's [Ghidra Version Tracking workflow](https://chdk.fandom.com/wiki/Ghidra_Version_Tracking_workflow_for_porting), retrieved 2026-10-17, recommends same-architecture and similar DryOS/release-era sources, importing stubs first, then matching exact symbol names and sufficiently long exact instruction mnemonics. Matches are candidates until call graph, literals, references, and behavior agree.

## 7. Reference-port knowledge that transfers safely

At r5491, G5 X, M10, and SX710 boot sources copy firmware regions to RAM, replace a RAM-resident `CreateTask` instruction sequence with an absolute Thumb jump, and substitute selected task entry pointers in `CreateTask_my`; they also create a separate CHDK SpyTask. See [G5 X `boot.c`](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/platform/g5x/sub/100c/boot.c), [M10 `boot.c`](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/platform/m10/sub/110d/boot.c), and [SX710 `boot.c`](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/platform/sx710hs/sub/100a/boot.c).

This verifies a historical **RAM-resident extension pattern**, not a working GM1.10C hook. Even the reference hook locations differ (`0xBFE149E4`, `0xBFE14A40`, and `0xBFE14A3C` respectively). GM1.10C needs its own copy destination, instruction preimage, task pointers, cache behavior, and memory-safety proof. No payload or patch is authorized.

## 8. Reproducibility and stopping conditions

Stop and return to documentation if any of the following occurs:

- the ROM size or hash differs;
- a proposed block or stub relies only on GM1.10E/reference-port addresses;
- disassembly requires forcing code through a proven table, string, or fill region;
- a script proposes writing the input file or exporting proprietary bytes;
- installation versions differ materially from the recorded dependencies;
- the analysis begins producing a camera-executable payload.

Only analyst-authored scripts, addresses with concise evidence, source URLs, hashes, and confidence labels may later be reviewed for commit. The ROM and Ghidra project remain local and ignored.

