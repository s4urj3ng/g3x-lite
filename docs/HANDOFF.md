# Agent handoff
Updated: 2026-10-16
Last agent: Gemini CLI
Branch/commit: `main` / Phase 0D `GM1.10C` target + Canon Basic ROM dumper safety review commit (resolve with `git log -1 --oneline`)

## Completed

- Followed `AGENTS.md` session protocol; remained strictly in **Phase 0D** (Phase 1 NOT started).
- Recorded owner-confirmed physical camera hardware facts (`E037`, **BLK-01 RESOLVED**): **Canon PowerShot G3 X**, internal firmware **`GM1.10C`**, public firmware **`1.1.0.0`**, Platform ID **`0x32A8` (`12968`)**, `PAL D` (camera serial number intentionally not stored).
- Documented that public firmware `1.1.0.0` has at least two distinct internal builds (`GM1.10C` on the owner's camera vs `GM1.10E` in `ranma`'s forum thread, `C011`), meaning `g3x_110e.patch` cannot be assumed binary-compatible with `GM1.10C` (`sub/110c`).
- Retrieved primary-source Wayback Machine snapshots of `https://chdk.fandom.com/wiki/Canon_Basic` (`20240527012744`), `https://chdk.fandom.com/wiki/Canon_Basic/Card_Setup` (`20220129011254`), and `https://chdk.fandom.com/wiki/Canon_Basic/Scripts/Dumper` (`20141220173812`, `20150905224847`, `20240724053956`) (`E038`–`E040`).
- Corrected earlier search-summary error (`C010`): `script.req` in the SD card root must contain the 17-byte ASCII string `"for DC_scriptdisk"` (SHA-256 `ef1fbfe9ac98f2fd2f88c2fdc8c6aa8472dc0dd2fafce7be3c3a8d89bd9c1733`), not an empty file, and `"SCRIPT"` goes at offset `0x1F0` of the FAT16/FAT32 partition VBR (`/dev/rdiskNs1` on macOS, never `/dev/diskN` MBR).
- Verified from primary dumper source (`E039`, `C008`) that DIGIC 6 detection checks `memcmp(0xFC020004,"gaonisoy",8) = 0` and sets `startaddr = 0xFC000000`, `os = "dry"`, `romsize = 0x2000000` (`33,554,432` bytes = 32 MiB).
- Performed a complete line-by-line safety audit of **Candidate A ("Universal dumper"**, 123 lines, `2,689` B LF, SHA-256 `3ca970ba22c2e9b50cf84bfc1f63074c84b01808129e0f1fbf6af25e4b362da5`) and **Candidate B ("Improved universal dumper"**, 166 lines, `3,820` B LF, SHA-256 `d06ff2ba31c973e70daa33c026b62ec8ba1b9b6b36063d5dd793e3894e0d0491`), plus documented the `2014`/`2015` MediaWiki `U+00A0` non-breaking space hazard (`E040`).
- Produced the pre-execution checklist, rollback plan, SHA-256 validation workflow, unresolved risk register (`RISK-01`–`RISK-03`), and explicit Owner Approval Gate (`Approval A3` & `Approval A2`) in `docs/FIRMWARE_ACQUISITION_PLAN.md`.
- Updated `docs/FIRMWARE_MATRIX.md`, `docs/RESEARCH_LOG.md`, `docs/FIRMWARE_ACQUISITION_PLAN.md`, `docs/PORT_READINESS.md`, `docs/PHASE1_ENTRY_CHECKLIST.md`, `docs/PROJECT_STATE.md`, and `docs/HANDOFF.md`.
- Performed zero camera interaction, zero SD card writes, zero payload generation, zero firmware download, and zero REA/Ghidra installation.

## Evidence anchors

- Owner physical camera screen (`GM1.10C`, `1.1.0.0`, `0x32A8` / `12968`, `PAL D`): owner-supplied firmware screen (`E037`, `C011`).
- Primary Canon Basic mechanism & card setup (`0x1F0` `"SCRIPT"`, `script.req` = `"for DC_scriptdisk"`, `extend.m`, Playback + `FUNC./SET`): Wayback snapshots `20240527012744` & `20220129011254` (`E038`, `C010`).
- Primary Canon Basic ROM dumper source & `0x2000000` (32 MiB) DIGIC 6 branch: Wayback snapshots `20141220173812`, `20150905224847`, `20240724053956` (`E039`, `C008`).
- MediaWiki `U+00A0` non-breaking space hazard in 2014/2015 snapshots vs pure-ASCII 2024 snapshot: byte-level inspection (`E040`).
- G3 X 1.00C Canon Basic dump archive (`PRIMARY.BIN` + `CBDUMPER.LOG`): forum posts 124672 and 124735 (`E029`).

## Next task

**STOP at the owner approval gate (`Approval A3` and `Approval A2` in `docs/FIRMWARE_ACQUISITION_PLAN.md` §5.2).** Do not generate an SD card payload, write to any disk device, or start Phase 1 until the owner explicitly responds:

1. If the owner approves **`Approval A3`** and requests help preparing `extend.m` and `script.req` locally (or prepares the card themselves per `docs/FIRMWARE_ACQUISITION_PLAN.md` §4): verify exact byte sizes and SHA-256 hashes before any camera use.
2. Once the owner executes the dump on `GM1.10C`, places `PRIMARY.BIN` and `CBDUMPER.LOG` under `private/firmware/g3x/110c/`, and grants **`Approval A2` (Phase 1 entry)**: run the §4.4 validation commands (verify `33,554,432` bytes, `"gaonisoy"` at `0x20004`, `"GM1.10C"` string, and SHA-256), record the hash in `docs/FIRMWARE_MATRIX.md`, and begin Phase 1 per `docs/PHASE1_ENTRY_CHECKLIST.md`.

Exact next command:

```sh
git status --short && git log -1 --oneline && sed -n '1,110p' docs/FIRMWARE_ACQUISITION_PLAN.md
```

## Blockers

- **BLK-01**: **RESOLVED** — Physical camera confirmed as `GM1.10C` (`1.1.0.0`, `0x32A8` / `12968`, `PAL D`, `E037`).
- **BLK-02**: No verified `GM1.10C` `PRIMARY.BIN` image acquired yet (awaiting owner approval `Approval A3` and S1 dump execution).
- **BLK-03**: `g3x_110e.patch` (attachment 16495) remains blocked to guest access and targets `GM1.10E` rather than `GM1.10C` (`C011`).
- **BLK-04**: Unresolved 1080p HDMI live-view crash / memory layout; requires Phase 1 static analysis.
- **BLK-05**: Explicit owner approval required for S1 on-camera dump execution (`Approval A3`) and Phase 1 entry (`Approval A2`).

## Safety

Phase 0D remains in effect. Do NOT execute scripts on the camera, generate or copy executable payloads onto an SD card, update/flash firmware, download proprietary binaries, install REA/Ghidra, or start Phase 1 without explicit human sign-off.
