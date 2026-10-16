# Phase 0 research report

Updated: 2026-10-16

## Executive finding

An offline G3 X reverse-engineering project is feasible, but a safe implementation project is not yet ready to begin. Public primary evidence establishes the camera family, official update path, and a historical proof-of-concept CHDK port. It does **not** establish a complete or stable G3 X port, validated dumps for every firmware revision, safe RAM regions, or feature-specific patch points.

The most defensible next target is firmware `GM1.20A` (Canon marketing version 1.2.0.0), because Canon identifies 1.2.0.0 as the update from versions through 1.1.0.0 and the historical CHDK author published a minimal 1.20A build. No binary should be acquired, analyzed, or executed until its provenance and hash are recorded locally and the owner explicitly approves Phase 1.

## Verified findings

### Firmware revisions

- **1.1.0.0 is official.** Canon says it adds EVF-DC2 support and applies to cameras selected by serial-number criteria. Source: <https://www.usa.canon.com/support/canon-product-advisories/firmware-notice-powershot-g3-x-firmware-version-1-1-0-0> (retrieved 2026-10-16).
- **1.2.0.0 is official and supersedes versions through 1.1.0.0.** Canon says it adds `image.canon` support. Source: <https://www.usa.canon.com/support/canon-product-advisories/firmware-notice-powershot-g3-x-firmware-version-1-2-0-0> (retrieved 2026-10-16).
- **Canon's public notices do not enumerate every factory firmware.** The labels `1.00C`, `GM1.10E`, and `GM1.20A` are evidenced by the CHDK forum artifacts, not by the two Canon notices. Their relationship to the user-facing versions is plausible and internally consistent, but must be verified from a legally acquired local image or camera version screen.

### Historical CHDK work

- A 2015 forum post reports a 32 MiB `PRIMARY.BIN` dump identified as G3 X 1.00C. A CHDK contributor replied that the dump looked correct. The linked proprietary dump was not downloaded or hashed in this research. Source: <https://chdk.setepontos.com/d/12600-g3-x-100c-fw-dump> (retrieved 2026-10-16).
- A later author (`ranma`) reported a port booting in playback mode and showing initial CHDK messages, with only `InitFileModules` hooked at that stage. The author later attached a `g3x_110e.patch` plus binaries and described four minimal hooks: keyboard, file-module initialization, PTP remote file write, and an FI2 boot workaround. Source: <https://chdk.setepontos.com/d/12600-g3-x-100c-fw-dump?page=2> (retrieved 2026-10-16).
- The same thread contains a 1.20A binary attachment and a reported comparison in which the 1.10E and 1.20A main-firmware stub addresses were effectively unchanged. This is author-supplied evidence, not an independently reproduced binary comparison. The author also reported live-view instability, especially with 1080p HDMI, before later saying a memory-placement change *seemed* to help and needed more testing.
- The current CHDK mirror examined at commit `92208bf004e193c30b625065889bd533732a524b` has no `platform/g3x` directory and its commit history query for that path is empty. Therefore the forum patch was not shown to have entered the current mirrored trunk. Repository: <https://github.com/01luna/CHDK> (HEAD checked 2026-10-16).

**Conclusion:** the public record proves a partial proof of concept, not a supported or stable CHDK port. Statements about boot addresses, RAM ownership, CPU subcomponents, or hardware registers remain hypotheses until reproduced offline from a provenance-controlled image.

### Architecture and stock capability baseline

- Canon identifies the PowerShot G3 X as using a DIGIC 6 image processor. Source: <https://global.canon/en/c-museum/product/dcc831.html> (retrieved 2026-10-16).
- The historical port's generated-stub excerpt reports DryOS release 57 and a main firmware start at `0xfc020000`; this is useful secondary technical evidence but has not been independently reproduced here.
- Canon documents manual focus and AF lock as stock features. AF lock is unavailable in Servo AF. Canon's support specifications list approximately 5.9 shots/s with One-Shot focus and approximately 3.2 shots/s with Servo AF. Sources: <https://gdlp01.c-wss.com/gds/3/0300019293/02/psg3x-cu2-en.pdf> and <https://www.usa.canon.com/support/p/powershot-g3-x> (retrieved 2026-10-16; manual pp. 86, 91, 93, 213).
- Canon's manual states that standard movie recording stops automatically at 4 GB or approximately 29 minutes 59 seconds. Source: the same user guide, pp. 212-213.

## Feasibility by requested feature

| Feature | Phase 0 assessment | Evidence and missing proof |
|---|---|---|
| AF Lock | **Already present; UI simplification plausible** | Stock manual documents AF lock. A custom UI could expose it more directly, but no event procedure, property case, or safe hook is verified for G3 X. |
| Shutter latency | **Unknown; measurement-first** | Burst rate is documented, but it is not shutter lag. No controlled latency baseline, task trace, or responsible code path has been established. |
| Video recording limit | **Plausible but high-risk** | The stock 4 GB/~29:59 stop is verified. Whether the time and size checks can be safely altered, and whether filesystem, thermal, encoder, battery, or container constraints remain, is unknown. |
| Simplified UI | **Plausible as an overlay; incomplete port blocks implementation** | The historical port displayed CHDK messages and experimented with clean overlays, but it was unstable and not integrated into trunk. Replacing Canon UI is substantially riskier than an additive overlay. |

## REA and Ghidra assessment

REA is suitable for a later, offline, read-only experiment, not as proof of firmware support. At upstream HEAD `fe2a398dd9ab290ba6cb3411403d319cec8d07a2` on 2026-10-16, its documentation says the Ghidra provider supports macOS x64/arm64, requires Ghidra 12.1.x and a compatible 64-bit JDK (currently JDK 21), opens an ephemeral project with `-readOnly`, and exposes read-only analysis operations. Source: <https://github.com/morluto/rea> and <https://github.com/morluto/rea/blob/main/docs/installation.md>.

Important limitation: REA's advertised native target list emphasizes normal executable/container formats. A raw Canon ROM requires correct processor language, image base, memory blocks, and segmentation. No source reviewed here proves that REA can supply those G3 X-specific import decisions. Ghidra itself, CHDK's `finsig_thumb2`, and version-tracking against a known DIGIC 6 port are therefore the likely core workflow; REA may be a read-only query layer after a correctly constructed project exists.

No REA, Ghidra, Java, MCP, or toolchain installation/configuration was performed.

## Actionable gated plan

### Complete Phase 0

1. Owner reads the installed camera firmware version using Canon's documented, non-invasive UI procedure; record the exact display without connecting or executing code.
2. Recover the forum `g3x_110e.patch` attachment and metadata without downloading firmware binaries. Record byte size and SHA-256 for the patch, then audit its complete diff against the exact CHDK base revision it expects.
3. Locate an authoritative source or repository history for the patch's base revision. Do not assume the current mirror is compatible.
4. Establish lawful provenance for a target firmware image. Keep it outside Git; record acquisition method, byte size, SHA-256, and version strings. Do not publish it.
5. Verify architecture, DryOS release, firmware start, ROM layout, and version strings independently from that image. Treat forum values only as comparison candidates.
6. Measure stock behavior from documentation or non-invasive owner observations: AF-lock workflow, shutter latency definition and test protocol, movie mode/codec/card combinations, and UI pain points.

### Proposed Phase 1 (requires explicit owner approval)

1. Create a quarantined offline analysis workspace and hash the immutable input.
2. Install pinned Ghidra/JDK versions only after reviewing their checksums and licenses; do not register REA/MCP yet.
3. Import a copy of the image with independently justified processor and memory map. Save the import recipe and Ghidra version.
4. Run only reviewed CHDK signature-analysis tools against the copy; capture command, tool commit, output hash, and warnings.
5. Compare 1.10E/1.20A symbols and the historical patch. Require two independent evidence paths before accepting an address or function identity.
6. Produce static call graphs for AF, capture sequencing, movie stop checks, and UI drawing. Do not patch or execute.
7. Gate any later hardware phase on a reviewed threat model, recovery plan, reversible loader, exact firmware match, and separate written approval.

## Risk register

| Risk | Current control | Exit condition |
|---|---|---|
| Wrong firmware/revision | No binary work; exact version remains unknown | Device version and input version independently match |
| Proprietary firmware redistribution | Firmware ignored and not downloaded during this session | Provenance record plus private storage policy |
| False symbols/load map | Forum addresses marked unverified | Reproducible import and independent signature/cross-version confirmation |
| Incomplete port damages data or camera | No execution or hardware work | Reviewed loader/recovery/test plan and explicit phase approval |
| Video-limit change causes corruption/thermal failure | No patch design yet | Static path analysis plus later staged safety plan |
| Agent/tool supply-chain risk | No installers or downloaded scripts executed | Pin, review, hash, and approve each tool before installation |

## Confidence summary

- **High:** official 1.1.0.0 and 1.2.0.0 notices; DIGIC 6; stock AF lock/manual focus; published recording stop and continuous-shooting rates.
- **Medium:** existence, revision targets, and incomplete state of the historical CHDK work, because the developer's own forum posts and attachments are primary for that work but have not been reproduced.
- **Low / unknown:** firmware memory map, CPU modes beyond the public DIGIC label, safe RAM regions, exact hook addresses, dump authenticity/hashes, and exploitability.
