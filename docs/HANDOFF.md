# Agent handoff
Updated: 2026-10-17
Last agent: Gemini CLI
Canonical repository (SOLE source of truth): `/Users/avp/project/g3x-lite` (`origin`: `https://github.com/s4urj3ng/g3x-lite`)
Retired backup repository (DO NOT USE): `/Users/avp/Downloads/g3x-lite`
Branch/commit: `main` synchronized with `origin/main` (resolve with `git -C /Users/avp/project/g3x-lite log -1 --oneline`)

## Completed

- Verified Candidate A ("Universal dumper") provenance, 123-line / 2,689-byte pure 7-bit ASCII text, and exact SHA-256 (`3ca970ba22c2e9b50cf84bfc1f63074c84b01808129e0f1fbf6af25e4b362da5`), and saved a byte-for-byte copy at [`firmware/tools/extend.m`](file:///Users/avp/project/g3x-lite/firmware/tools/extend.m) (`E041`).
- Performed read-only preflight verification of `/Volumes/G3X_DUMP` (`/dev/disk3s1`, 63.9 GB MBR + MS-DOS FAT32, `BPB_TotSec32 = 124,733,440`) and confirmed `/Volumes/G3X_DUMP/script.req` is 17 bytes (`for DC_scriptdisk`, SHA-256 `60e6a567e9c0731d95415e0fb2c687efd2d6309f766edee17d127d77597d1767`, `E041`, `C012`).
- Verified `/Users/avp/Downloads/g3x-sd-backup/bootsector-original.bin` is a 512-byte FAT32 VBR matching `/dev/disk3s1` (`SHA-256 = 16947123219f03af103e9faa5da4992464e8c878c65a4f09354b495a430b6364`) with `0x1F0–0x1F5` = `00 00 00 00 00 00` and `0x1FE–0x1FF` = `55 aa` (`E041`).
- Documented static safety review and preflight report in `docs/FIRMWARE_ACQUISITION_PLAN.md` §6 and `docs/RESEARCH_LOG.md` (`E041`, `C012`), including `RISK-04` (64 GB SDXC card formatted on macOS as MBR + FAT32 must NOT be re-formatted in-camera prior to dumping, as in-camera formatting would convert >32 GB media to `exFAT`).
- Performed zero SD boot-sector writes, did NOT copy `extend.m` onto `/Volumes/G3X_DUMP`, and performed zero camera operations.

## Evidence anchors

- Preflight verification of `firmware/tools/extend.m`, `/Volumes/G3X_DUMP/script.req`, and `/Users/avp/Downloads/g3x-sd-backup/bootsector-original.bin`: local inspection (`E041`, `C012`).
- Owner physical camera screen (`GM1.10C`, `1.1.0.0`, `0x32A8` / `12968`, `PAL D`): owner-supplied firmware screen (`E037`, `C011`).
- Primary Canon Basic mechanism & card setup (`0x1F0` `"SCRIPT"`, `script.req` = `"for DC_scriptdisk"`, `extend.m`, Playback + `FUNC./SET`): Wayback snapshots `20240527012744` & `20220129011254` (`E038`, `C010`).
- Primary Canon Basic ROM dumper source & `0x2000000` (32 MiB) DIGIC 6 branch: Wayback snapshots `20141220173812`, `20150905224847`, `20240724053956` (`E039`, `C008`, `E040`).

## Next task

**Work exclusively in `/Users/avp/project/g3x-lite` and STOP at the owner approval gate (`Approval A3` and `Approval A2` in `docs/FIRMWARE_ACQUISITION_PLAN.md` §5).** `firmware/tools/extend.m` is ready for owner review. Do not copy `extend.m` to `/Volumes/G3X_DUMP`, write `"SCRIPT"` to `/dev/rdisk3s1`, or run on the camera until the owner explicitly approves:

1. Upon owner approval of **`Approval A3`**: copy `firmware/tools/extend.m` to `/Volumes/G3X_DUMP/extend.m` (verify SHA-256 `3ca970ba22c2e9b50cf84bfc1f63074c84b01808129e0f1fbf6af25e4b362da5`), unmount `/dev/disk3s1`, write `"SCRIPT"` at offset `0x1F0` (`496`) of `/dev/rdisk3s1`, verify readback, and eject cleanly.
2. Once the owner executes the dump on `GM1.10C`, places `PRIMARY.BIN` and `CBDUMPER.LOG` under `/Users/avp/project/g3x-lite/private/firmware/g3x/110c/`, and grants **`Approval A2` (Phase 1 entry)**: run the §4.4 validation commands (verify `33,554,432` bytes, `"gaonisoy"` at `0x20004`, `"GM1.10C"` string, and SHA-256), record the hash in `docs/FIRMWARE_MATRIX.md`, and begin Phase 1 per `docs/PHASE1_ENTRY_CHECKLIST.md`.

Exact next command:

```sh
git -C /Users/avp/project/g3x-lite status --short && shasum -a 256 /Users/avp/project/g3x-lite/firmware/tools/extend.m && sed -n '335,380p' /Users/avp/project/g3x-lite/docs/FIRMWARE_ACQUISITION_PLAN.md
```

## Blockers

- **BLK-01**: **RESOLVED** — Physical camera confirmed as `GM1.10C` (`1.1.0.0`, `0x32A8` / `12968`, `PAL D`, `E037`).
- **BLK-02**: No verified `GM1.10C` `PRIMARY.BIN` image acquired yet (`firmware/tools/extend.m` staged and preflight verified; awaiting owner review and `Approval A3`).
- **BLK-03**: `g3x_110e.patch` (attachment 16495) remains blocked to guest access and targets `GM1.10E` rather than `GM1.10C` (`C011`).
- **BLK-04**: Unresolved 1080p HDMI live-view crash / memory layout; requires Phase 1 static analysis.
- **BLK-05**: Explicit owner approval required before copying `extend.m` to SD / writing VBR `"SCRIPT"` (`Approval A3`) and before Phase 1 entry (`Approval A2`).

## Safety

Do NOT modify the SD boot sector, copy `extend.m` to `/Volumes/G3X_DUMP`, execute scripts on the camera, update/flash firmware, or start Phase 1 binary analysis without explicit human sign-off.
