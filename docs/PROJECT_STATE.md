# Project state
Updated: 2026-10-17
Canonical repository: `/Users/avp/project/g3x-lite` (`origin`: `https://github.com/s4urj3ng/g3x-lite`; `/Users/avp/Downloads/g3x-lite` is a retired read-only backup)
Phase: 0D / Phase 1 Dumper Preflight Preparation (No on-camera execution or Phase 1 binary analysis started)
Status: Verified Candidate A Canon Basic Universal Dumper staged at `firmware/tools/extend.m` (SHA-256 `3ca970ba22c2e9b50cf84bfc1f63074c84b01808129e0f1fbf6af25e4b362da5`, ready for owner review); `/Volumes/G3X_DUMP/script.req` (17 B) and `/Users/avp/Downloads/g3x-sd-backup/bootsector-original.bin` (512 B, `0x1F0–0x1F5` all zero) verified (`E041`). Stopped at owner review/approval gate.
Host target: MacBook Pro 16-inch 2019 Intel macOS (environment not inspected).
Agents: Codex, Claude Code, Gemini CLI (interchangeable per AGENTS.md protocol).
Reverse tooling: REA/Ghidra intentionally NOT installed or configured.
Camera: Canon PowerShot G3 X; internal firmware **`GM1.10C`**, public firmware **`1.1.0.0`**, Platform ID **`0x32A8` (`12968`)**, `PAL D` (**BLK-01 RESOLVED**, E037; serial number intentionally omitted).
Firmware dump: NOT acquired yet (BLK-02). `firmware/tools/extend.m` (Candidate A) and `/Volumes/G3X_DUMP` preflight verified; awaiting owner review before copying `extend.m` to SD or writing `"SCRIPT"` to VBR.
CHDK G3 X port: Historical partial `1.10E`/`1.20A` proof of concept verified from author posts; patch attachment 16495 unavailable via guest access and targets `GM1.10E` rather than owner's `GM1.10C` (BLK-03, C011).
Hardware tests: NONE authorized or executed.

## Decisions

- Standardized `/Users/avp/project/g3x-lite` (tracking `https://github.com/s4urj3ng/g3x-lite`) as the single source of truth; `/Users/avp/Downloads/g3x-lite` is preserved untouched as a read-only backup and must not be used for future work.
- Remain at the pre-execution safety boundary; do not write to the SD boot sector, do not copy `extend.m` onto `/Volumes/G3X_DUMP`, and do not execute on the camera without explicit owner approval.
- Saved verified Candidate A ("Universal dumper", 123 lines, 2,689 B LF, pure 7-bit ASCII, SHA-256 `3ca970ba22c2e9b50cf84bfc1f63074c84b01808129e0f1fbf6af25e4b362da5`) to `firmware/tools/extend.m` and tracked `firmware/tools/**` in `.gitignore` while keeping all firmware binaries ignored (`E041`).
- Verified `/Volumes/G3X_DUMP/script.req` (17 B, `"for DC_scriptdisk"`, SHA-256 `60e6a567e9c0731d95415e0fb2c687efd2d6309f766edee17d127d77597d1767`, correcting earlier transcription `C012`) and `/Users/avp/Downloads/g3x-sd-backup/bootsector-original.bin` (512 B, SHA-256 `16947123219f03af103e9faa5da4992464e8c878c65a4f09354b495a430b6364`, `0x1F0–0x1F5` = `00 00 00 00 00 00`, `E041`).

## Current evidence

- Physical camera screen confirms `Canon PowerShot G3 X`, internal `GM1.10C`, public `1.1.0.0`, `PLATFORMID = 0x32A8` (`12968`), `PAL D` (E037); distinguishes `GM1.10C` from `GM1.10E` under public `1.1.0.0` (C011).
- Archived `chdk.fandom.com/wiki/Canon_Basic` (`20240527012744`) and `Canon_Basic/Card_Setup` (`20220129011254`) verify partition boot sector offset `0x1F0` = `"SCRIPT"`, `script.req` = `"for DC_scriptdisk"` (17 B), `extend.m` script name, and Playback + `FUNC./SET` trigger (E038, C010).
- Archived `chdk.fandom.com/wiki/Canon_Basic/Scripts/Dumper` (`20141220173812`, `20150905224847`, `20240724053956`) provides the verbatim Canon Basic dumper source checking `memcmp(0xFC020004,"gaonisoy",8) = 0`, setting `startaddr = 0xFC000000` and `romsize = 0x2000000` (`33,554,432` B), and writing `A/PRIMARY.BIN` and `A/CBDUMPER.LOG` via `Fopen_Fut`/`Fwrite_Fut`/`Fclose_Fut` (E039, C008).
- Preflight inspection (`E041`, `C012`) confirms `firmware/tools/extend.m` (2,689 B, SHA-256 `3ca970ba22c2e9b50cf84bfc1f63074c84b01808129e0f1fbf6af25e4b362da5`), `/Volumes/G3X_DUMP/script.req` (17 B, SHA-256 `60e6a567e9c0731d95415e0fb2c687efd2d6309f766edee17d127d77597d1767`), and `/Users/avp/Downloads/g3x-sd-backup/bootsector-original.bin` (512 B, SHA-256 `16947123219f03af103e9faa5da4992464e8c878c65a4f09354b495a430b6364`, `0x1F0–0x1F5` = `00 00 00 00 00 00`).
- r5491 (`21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6`) and r5492 (`8cded093bccce82ffe34d904da640fc55e087314`) reference ports, LED GPIO differences (`0xd20b0884`/`0xd20b0810` vs `0xd20b0994`, E025/C006), `tools/Makefile` Capstone link rules (E035/C007), and `.gitignore` rules (`private/` vs `dumps/`, E036) remain verified.

## Open questions / blockers

- **BLK-01**: **RESOLVED** — Physical camera confirmed as `GM1.10C` (`1.1.0.0`, `0x32A8` / `12968`, `PAL D`, E037).
- **BLK-02**: No verified `GM1.10C` `PRIMARY.BIN` image acquired yet. `firmware/tools/extend.m` and `/Volumes/G3X_DUMP` preflight are complete (`docs/FIRMWARE_ACQUISITION_PLAN.md` §6), awaiting owner review and execution approval.
- **BLK-03**: Historical patch `g3x_110e.patch` (attachment 16495) remains blocked to guest access and targets `GM1.10E` rather than `GM1.10C` (C011); `GM1.10C` requires clean-room symbol/task extraction in Phase 1.
- **BLK-04**: Unresolved 1080p HDMI live-view crash / memory layout; requires Phase 1 static analysis.
- **BLK-05**: Explicit owner approval required before copying `extend.m` to `/Volumes/G3X_DUMP`, writing `"SCRIPT"` to `/dev/rdisk3s1` (`0x1F0`), or executing the dumper on-camera (`Approval A3` / `Approval A2`).

## Next recommended task

**STOP and wait for owner review of `firmware/tools/extend.m` and explicit approval** (`Approval A3` in `docs/FIRMWARE_ACQUISITION_PLAN.md` §5) before copying `extend.m` to `/Volumes/G3X_DUMP/extend.m` or writing `"SCRIPT"` to `/dev/rdisk3s1` at offset `0x1F0`.

See `firmware/tools/extend.m`, `docs/FIRMWARE_ACQUISITION_PLAN.md`, `docs/FIRMWARE_MATRIX.md`, `docs/PORT_READINESS.md`, `docs/PHASE1_ENTRY_CHECKLIST.md`, and `docs/RESEARCH_LOG.md`.
