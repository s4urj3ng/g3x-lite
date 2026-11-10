# PORT-42: FULL_HOOKS=1 Full CHDK Build with FINSIG-Confirmed Hooks

## 1. Overview

The `FULL_HOOKS=1` opt-in switch enables CHDK task hooks for the standard full CHDK build (`PLATFORM=g3x PLATFORMSUB=110c`, toolchain `toolchains/gcc-arm-none-eabi-5_4-2016q3`) where target task addresses are confirmed in `reference/finsig_gm110c/stubs_entry.S` (with zero uncertainty) or established in existing `VERIFIED` records.

- **Stock / Disabled Hooks**: Hooks requiring unverified internal addresses (`INFERRED-only`) remain stock and on the TODO list.
- **Card-Write Invariants**: CHDK runtime card writes remain strictly suppressed (`-DG3X_DISABLE_CARD_WRITES=1`, `-DOPT_DISABLE_FILE_WRITES=1`, linker `--wrap` options unchanged from PORT-41).
- **Candidate Invariance**: All candidate builds (PORT-24..40) remain bit-identical.
- **Switch Off Invariance**: Without `FULL_HOOKS=1`, the full build produces the standard PORT-41 distribution.
- **ROM Slices**: Zero ROM slices were read (`0` bytes) as all hook addresses are confirmed in `reference/finsig_gm110c/stubs_entry.S`.

---

## 2. Hook Evaluation Table

| Hook | Address(es) | Label | Sibling Citation | Enabled (yes/no) | Notes / Reason Left Disabled |
|---|---|---|---|---|---|
| `task_PhySw` | `0xFC1283AD` | `FINSIG` / `VERIFIED` | `chdk-port/platform/g7x/sub/100d/boot.c:16-25, 400` | yes | Intercepted in `CreateTask_my`; expands stack to 0x2000 and branches to `mykbd_task`. |
| `task_InitFileModules` | `0xFC0BD071` | `FINSIG` / `VERIFIED` | `chdk-port/platform/g7x/sub/100d/boot.c:140-144, 410-434` | yes | Intercepted in `CreateTask_my`; signals `core_spytask_can_start()` with `r1=1` completion argument. |
| `task_CaptSeq` | `0xFC06A001` | `FINSIG` | `chdk-port/platform/g7x/sub/100d/boot.c:103-108`<br>`chdk-port/platform/g7x/sub/100d/capt_seq.c:63-65` | yes | Intercepted in `CreateTask_my` via `capt_seq_task`; safe pass-through trampoline to stock DryOS entry (internal raw develop hooks unverified/INFERRED-only). |
| `task_FileWrite` | `0xFC25F3A7` | `FINSIG` | `chdk-port/platform/g7x/sub/100d/boot.c:126-131`<br>`chdk-port/platform/g7x/sub/100d/filewrite.c:110-115` | yes | Intercepted in `CreateTask_my` via `filewritetask`; safe pass-through trampoline to stock DryOS entry (async card write hooks suppressed and unverified/INFERRED-only). |
| `task_MovieRecord` | `0xFC09AC19` | `FINSIG` | `chdk-port/platform/g7x/sub/100d/boot.c:134-138`<br>`chdk-port/platform/g5x/sub/100c/boot.c:139-144` | no | Disabled across sibling DIGIC 6 ports; movie recording task hooks and video bitrate tables are unverified (INFERRED-only). |
| `task_ExpDrv` | `0xFC2C136F` | `FINSIG` | `chdk-port/platform/g7x/sub/100d/boot.c:111-116`<br>`chdk-port/platform/g5x/sub/100c/boot.c:121-125` | no | Disabled in sibling g7x; internal exposure control state machine and calibration tables are unverified (INFERRED-only). |
| `task_DvlpSeqTask` | `0xFC07B637` | `FINSIG` | `chdk-port/platform/g7x/sub/100d/boot.c:118-123`<br>`chdk-port/platform/g5x/sub/100c/boot.c:127-132` | no | Disabled across DIGIC 6 siblings; raw develop sequence internal addresses are unverified (INFERRED-only). |
| `task_TricInitTask` | `0xFC4E4B19` | `FINSIG` | `chdk-port/platform/g5x/sub/100c/boot.c:145-149` | no | FI2-specific boot initialization task not applicable to standard DISKBOOT builds. |
| `task_TouchPanel` | `0xFC12E74F` | `FINSIG` | `reference/finsig_gm110c/stubs_entry.S:341` | no | Touch panel events are handled directly by Canon firmware UI; not hooked in sibling ports. |
