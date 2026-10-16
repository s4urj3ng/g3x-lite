# Firmware revision matrix

| Revision | Official source | Dump/provenance | Hash | CHDK evidence | Status |
|---|---|---|---|---|---|
| **1.1.0.0 / `GM1.10C` (owner device)** | Owner-confirmed physical camera firmware screen (`Canon PowerShot G3 X`, `GM1.10C`, `1.1.0.0`, Platform ID `0x32A8` / `12968`, `PAL D`; E037) | None acquired yet (S1 owner dump planned, awaiting Gate A2/A3 approval) | Pending dump | No prior CHDK port or patch specifically targeting `GM1.10C`; relationship to `GM1.10E` (`g3x_110e.patch`) unverified | **CONFIRMED TARGET DEVICE (`BLK-01` resolved; `BLK-02` pending dump)** |
| 1.00C | No Canon notice located | Forum author (`Nippey`) reported a 32 MiB `PRIMARY.BIN` + `CBDUMPER.LOG`; proprietary link not accessed (E004, E029) | Unknown | 2015 stub-recovery work and `finsig_thumb2` test target (E033); no bootable port demonstrated in initial work | **Forum-evidenced only** |
| 1.1.0.0 / `GM1.10E` | [Canon 1.1.0.0 notice](https://www.usa.canon.com/support/canon-product-advisories/firmware-notice-powershot-g3-x-firmware-version-1-1-0-0) | No local image | Unknown | `g3x_110e.patch` and minimal binaries attached to [forum page 2](https://chdk.setepontos.com/d/12600-g3-x-100c-fw-dump?page=2); partial and unstable (E005) | **Official update; incomplete port (different internal build letter from owner's `GM1.10C`)** |
| 1.2.0.0 / `GM1.20A` | [Canon 1.2.0.0 notice](https://www.usa.canon.com/support/canon-product-advisories/firmware-notice-powershot-g3-x-firmware-version-1-2-0-0) | No local image | Unknown | Minimal 1.20A binary attached; author reported stubs nearly identical to 1.10E, not independently reproduced (E006, E032) | **Latest verified official; incomplete port** |

Retrieved/updated: 2026-10-16.
- Owner's physical camera screen confirms that public `1.1.0.0` exists as internal build `GM1.10C` (with Platform ID `0x32A8` = `12968` decimal and `PAL D`), proving that public `1.1.0.0` is not uniquely `GM1.10E` (E037, C011).
- Never store or commit camera serial numbers. Never add a version solely from earlier chat speculation.
