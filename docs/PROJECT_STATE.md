# Project state
Updated: 2026-10-16
Phase: 0D — Port Readiness Audit & Phase 1 S1 Dump Safety Review (Phase 1 NOT started)
Status: Physical target confirmed (`GM1.10C`, `0x32A8`); Canon Basic ROM dumper primary source recovered, audited line-by-line, and pre-execution checklist prepared in `docs/FIRMWARE_ACQUISITION_PLAN.md`. Stopped at owner approval gate (`Approval A3` / `Approval A2`).
Host target: MacBook Pro 16-inch 2019 Intel macOS (environment not inspected).
Agents: Codex, Claude Code, Gemini CLI (interchangeable per AGENTS.md protocol).
Reverse tooling: REA/Ghidra intentionally NOT installed or configured.
Camera: Canon PowerShot G3 X; internal firmware **`GM1.10C`**, public firmware **`1.1.0.0`**, Platform ID **`0x32A8` (`12968`)**, `PAL D` (**BLK-01 RESOLVED**, E037; serial number intentionally omitted).
Firmware dump: NOT acquired yet (BLK-02). Owner prefers Strategy S1 (read-only Canon Basic dump of own `GM1.10C` camera); verbatim primary source and safety review completed.
CHDK G3 X port: Historical partial `1.10E`/`1.20A` proof of concept verified from author posts; patch attachment 16495 unavailable via guest access and targets `GM1.10E` rather than owner's `GM1.10C` (BLK-03, C011).
Hardware tests: NONE authorized or executed.

## Decisions

- Remain in Phase 0D; do not execute scripts on the camera, generate SD payloads, or start Phase 1 binary analysis without explicit owner approval.
- Recorded owner-confirmed hardware target: `Canon PowerShot G3 X`, internal build `GM1.10C`, public version `1.1.0.0`, `PLATFORMID = 0x32A8` (`12968`), `PAL D` (E037); camera serial number is never stored.
- Documented that public firmware `1.1.0.0` encompasses at least two distinct internal builds (`GM1.10C` on the owner's camera vs `GM1.10E` in `ranma`'s forum thread, C011). Therefore `GM1.10C` (`sub/110c`) requires independent symbol and task extraction from the owner's `GM1.10C` `PRIMARY.BIN`.
- Recovered verbatim primary-source Canon Basic scripts from archived `chdk.fandom.com/wiki/Canon_Basic/Scripts/Dumper` and `Canon_Basic/Card_Setup` pages (E038–E040), correcting an earlier search-summary error (`script.req` must contain the 17-byte string `"for DC_scriptdisk"`, not an empty file, C010) and confirming from code that DIGIC 6 (`"gaonisoy"` at `0xFC020004`) dumps `romsize = 0x2000000` (`33,554,432` bytes = 32 MiB) from `0xFC000000` (C008).
- Completed line-by-line safety review of Candidate A ("Universal dumper", 123 lines, SHA-256 `3ca970ba22c2e9b50cf84bfc1f63074c84b01808129e0f1fbf6af25e4b362da5`) and Candidate B ("Improved universal dumper", 166 lines, SHA-256 `d06ff2ba31c973e70daa33c026b62ec8ba1b9b6b36063d5dd793e3894e0d0491`), confirming zero Flash/ROM/EEPROM/NVRAM write calls and documenting the `2014`/`2015` MediaWiki `U+00A0` copy-paste hazard (E040).

## Current evidence

- Physical camera screen confirms `Canon PowerShot G3 X`, internal `GM1.10C`, public `1.1.0.0`, `PLATFORMID = 0x32A8` (`12968`), `PAL D` (E037); distinguishes `GM1.10C` from `GM1.10E` under public `1.1.0.0` (C011).
- Archived `chdk.fandom.com/wiki/Canon_Basic` (`20240527012744`) and `Canon_Basic/Card_Setup` (`20220129011254`) verify partition boot sector offset `0x1F0` = `"SCRIPT"`, `script.req` = `"for DC_scriptdisk"` (17 B), `extend.m` script name, and Playback + `FUNC./SET` trigger (E038, C010).
- Archived `chdk.fandom.com/wiki/Canon_Basic/Scripts/Dumper` (`20141220173812`, `20150905224847`, `20240724053956`) provides the verbatim Canon Basic dumper source checking `memcmp(0xFC020004,"gaonisoy",8) = 0`, setting `startaddr = 0xFC000000` and `romsize = 0x2000000` (`33,554,432` B), and writing `A/PRIMARY.BIN` and `A/CBDUMPER.LOG` via `fopen_fn`/`fwrite_fn`/`fclose_fn` (E039, C008).
- `2014`/`2015` MediaWiki `<pre>` snapshots of `Canon_Basic/Scripts/Dumper` contain 9 `U+00A0` bytes whereas the `2024-07-24` snapshot is 100% pure 7-bit ASCII (E040).
- Forum posts 124672 and 124735 record a 2015 G3 X 1.00C archive containing `PRIMARY.BIN (32MB)` and `CBDUMPER.LOG` produced 10 days after the `2015-09-05` dumper wiki revision (E029, E039).
- r5491 (`21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6`) and r5492 (`8cded093bccce82ffe34d904da640fc55e087314`) reference ports, LED GPIO differences (`0xd20b0884`/`0xd20b0810` vs `0xd20b0994`, E025/C006), `tools/Makefile` Capstone link rules (E035/C007), and `.gitignore` rules (`private/` vs `dumps/`, E036) remain verified.

## Open questions / blockers

- **BLK-01**: **RESOLVED** — Physical camera confirmed as `GM1.10C` (`1.1.0.0`, `0x32A8` / `12968`, `PAL D`, E037).
- **BLK-02**: No verified `GM1.10C` `PRIMARY.BIN` image acquired yet. Pre-execution checklist and verified dumper source are ready in `docs/FIRMWARE_ACQUISITION_PLAN.md` §3–§4, awaiting owner approval (`Approval A3`).
- **BLK-03**: Historical patch `g3x_110e.patch` (attachment 16495) remains blocked to guest access and targets `GM1.10E` rather than `GM1.10C` (C011); `GM1.10C` requires clean-room symbol/task extraction in Phase 1.
- **BLK-04**: Unresolved 1080p HDMI live-view crash / memory layout; requires Phase 1 static analysis.
- **BLK-05**: Explicit owner approval required before any SD-card preparation / on-camera Canon Basic dump execution (`Approval A3`) and before entering Phase 1 (`Approval A2`).

## Next recommended task

**STOP and wait for explicit owner approval** on `Approval A3` (on-camera S1 Canon Basic dump execution) and `Approval A2` (Phase 1 entry after dump validation) in `docs/FIRMWARE_ACQUISITION_PLAN.md` §5.2. Do not generate SD card payloads, touch camera hardware, or start Phase 1 without explicit human sign-off.

See `docs/FIRMWARE_ACQUISITION_PLAN.md`, `docs/FIRMWARE_MATRIX.md`, `docs/PORT_READINESS.md`, `docs/PHASE1_ENTRY_CHECKLIST.md`, and `docs/RESEARCH_LOG.md`.
