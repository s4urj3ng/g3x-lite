# PORT-18: Owner First-Boot Trial and Recovery Plan

**Target device**: Canon PowerShot G3 X `[VERIFIED: README.md:3; docs/FIRMWARE_ACQUISITION_PLAN.md:18]`.
**Target firmware**: internal build `GM1.10C`, platform ID `0x32A8` (`12968` decimal) `[VERIFIED: docs/FIRMWARE_ACQUISITION_PLAN.md:19, 21; chdk-port/platform/g3x/sub/110c/g3x_trace.h:7; tools/build_candidate_port2a.py:232]`. DIGIC 6, DryOS 57 `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:6; tools/build_candidate_port2a.py:234]`.
**Safety gate**: hardware readiness of the candidate is `NO-GO` `[VERIFIED: docs/PORT16_CANDIDATE_BUILD.md:27, 438; tools/build_candidate_port2a.py:930]`. Phase 0 is read-only regarding firmware and camera hardware `[VERIFIED: AGENTS.md:18-19; docs/SAFETY.md:3-4]`, and any phase transition requires explicit human approval `[VERIFIED: AGENTS.md:22]`. Before any hardware test the owner must verify model/revision, reliable power, reversible loading, a known recovery path, owner approval, a test plan and rollback conditions `[VERIFIED: docs/SAFETY.md:7]`. This document and passing host checks do **not** grant that approval `[INFERRED: docs/SAFETY.md:8; AGENTS.md:22]`. Sections 2, 3 and 5 are steps the human owner performs by hand only after that separate approval; no agent performs them `[INFERRED: AGENTS.md:18-22]`.

**Label convention**: `VERIFIED` means the cited line(s) literally contain the value or statement. `INFERRED` means a reasoned reading of the cited lines that they do not state outright. `UNKNOWN` means no tracked line establishes it. Every firmware address, offset, symbol value and CPU mode below is cited to a tracked doc or stub, or labelled `UNKNOWN`.

**Untracked files are not cited as evidence.** `docs/CHDK_PORT0D_BOOT_RECOVERY.md` and `chdk-port/loader/g3x/main_prototype.c` exist in some worktrees but are not tracked. `git ls-files` lists neither at this commit, and `.gitignore:39` ignores `chdk-port/*` with no re-include for `chdk-port/loader/` `[VERIFIED: .gitignore:39-50; absence checked with git ls-files, which has no file:line]`. Where a tracked doc relies on them, that tracked doc is cited and the claim is labelled to match.

**Inspector witness address alignment (resolved — P6)**: Candidate `boot_witness` is pinned at `0x0035F7A0` (Section `.data`, Type `D`, 16-byte aligned, 32 B) and `_end` at `0x00366CB0` `[VERIFIED: docs/PORT19_WITNESS_ADDRESS.md:17-20, 325-332; docs/PORT16_WITNESS_ADDRESS.md:15, 218; tools/build_candidate_port2a.py:54; tools/validate_candidate_port2a.py:48, 52; tools/port18_trial_preflight.py:50, 61]`. A local candidate build writes `candidate_port2a/witness_inspector_metadata.json`, `candidate_port2a/witness_inspector_payload.bin`, and `candidate_port2a/witness_inspector_gm110c.m` targeting `0x0035F7A0` `[VERIFIED: tools/build_candidate_port2a.py:802-805; docs/PORT19_WITNESS_ADDRESS.md:17-20, 348-366]`. The inspector builder/validator (`tools/build_witness_inspector.py:30, 37, 39, 42`, `tools/validate_witness_inspector.py:54, 73, 75, 78`) and preflight tool (`tools/port18_trial_preflight.py:50, 488-567`) all default to `candidate_port2a/`, pin `0x0035F7A0`, and reject the historical pre-correction `firmware/tools/` baseline fail-closed `[VERIFIED: docs/PORT19_WITNESS_ADDRESS.md:21-31, 60, 374-419]`. The tracked file `firmware/tools/witness_inspector_metadata.json` remains an unedited historical baseline and must never be copied to an SD card or staged `[VERIFIED: docs/PORT19_WITNESS_ADDRESS.md:60; INFERRED: AGENTS.md:14]`.

---

## 1. Preconditions

### 1.1 Preconditions (P1–P2 owner items, P3/P4/P6 resolved in PORT-19, P5 host check)

| ID | Precondition | Status |
|---|---|---|
| P1 | Owner phase-transition approval recorded | **OWNER ITEM (`UNKNOWN` until recorded by owner).** Required by `AGENTS.md:22` and `docs/SAFETY.md:7` `[VERIFIED]`. Status `UNKNOWN` until the human owner records explicit approval. |
| P2 | Physical camera internal build is `GM1.10C` | **OWNER ITEM (owner-verified before trial).** Recorded from the owner's diagnostic screen as E037 `[VERIFIED: docs/FIRMWARE_ACQUISITION_PLAN.md:14, 19; docs/RESEARCH_LOG.md:50]`. Public version `1.1.0.0` covers at least two internal builds, `GM1.10C` and `GM1.10E` `[VERIFIED: docs/FIRMWARE_ACQUISITION_PLAN.md:20]`, so the public version shown in menus is not enough `[INFERRED: docs/FIRMWARE_ACQUISITION_PLAN.md:20, 25]`. The inspector script also refuses to run its payload unless `"GM1.10C"` matches at `0xFC54E08D` `[VERIFIED: firmware/tools/witness_inspector_gm110c.m:42, 176-180]`. |
| P3 | `BOOTDISK` and `SCRIPT` VBR marker offsets per filesystem | **RESOLVED (`VERIFIED`).** GM1.10C `Mounter.c` (`0xFC37A4B6-0xFC37A680`, helper `0xFC37B2AE-0xFC37B2C2`, `make_bootable` `0xFC37B318-0xFC37B38A`) checks `"BOOTDISK"` (8 ASCII bytes) at VBR offset **`0x1E0`** (`480` dec) on **FAT32** (`0xFC37A5FA`, `0xFC37A606`, `0xFC37B3A8`) and at VBR offset **`0x40`** (`64` dec) on **FAT16** (`0xFC37A63A`, `0xFC37A650`) and **FAT12** (`0xFC37A63E`, `0xFC37A650`) `[VERIFIED: docs/PORT19_BOOTDISK_VBR.md:20-25, 67-72, 164-206]`. It checks `"SCRIPT"` (6 ASCII bytes) at VBR offset **`0x1F0`** (`496` dec) on **FAT12, FAT16, and FAT32** (`0xFC37A668-0xFC37A67C`, literal `0xFC37A7F0`) `[VERIFIED: docs/PORT19_BOOTDISK_VBR.md:29-34, 69-72, 208-222]`. **exFAT is `UNSUPPORTED` (`VERIFIED`)**: `0xFC37A55C` branches to exit `0xFC37A67E` before both marker checks, leaving `is_bootdisk = 0` and `is_scriptdisk = 0` `[VERIFIED: docs/PORT19_BOOTDISK_VBR.md:24, 33, 73-74, 138-155]`. `EOS_DEVELOP` is not checked by the inspected Mounter VBR routine (`0xFC37A4B6-0xFC37A680`, helper `0xFC37B2AE-0xFC37B2C2`) `[VERIFIED: docs/PORT19_BOOTDISK_VBR.md:40, 43]`; whether checked elsewhere in GM1.10C is `[UNKNOWN: docs/PORT19_BOOTDISK_VBR.md:41, 43-44]`. |
| P4 | `StartDiskboot` accepts the candidate's file encoding | **RESOLVED (`VERIFIED`).** GM1.10C production `StartDiskboot` (`0xFC05BBEA` → `0xFC05BC3C`) requires an **ENCODED** `A/DISKBOOT.BIN` (`dancingbits row 13, leading 0x00 byte`) `[VERIFIED: docs/PORT19_DISKBOOT_ENCODING.md:14-31]`. Validator/decoder `sub_fc54de38` (`0xFC54DE38`) rejects any file with `byte 0 != 0x00` (`0xFC54DE3A-0xFC54DE3C`, returning `1` → `"not executable\n"` at `0xFC05BC66-0xFC05BC68`), shifts the buffer left by 1 byte (`0xFC54DE4E-0xFC54DE5E`, decrementing local `r1` to `file_size - 1`), and calls `sub_fc42189c` (`0xFC42189C`) to decode `file_size - 1` bytes in-place using DancingBits Row 13 (`[6, 5, 3, 7, 0, 2, 4, 1]` at `0xFC7C0F8C` via `0xFC469180`) and `_dance` (`0xFC469188`), before `0xFC05BC7A` copies the decoded image to `0x40008000` (`0xFC0D9C9C` → `0xFC0007C0`) and branches to `0x8001` in Thumb state `[VERIFIED: docs/PORT19_DISKBOOT_ENCODING.md:17-22, 138-323]`. Raw `DISKBOOT.BIN` is incompatible (the raw loader at `0xFC0005A0` is the factory `RomStarter` rescue path) `[VERIFIED: docs/PORT19_DISKBOOT_ENCODING.md:19-22, 331-339]`. Candidate `candidate_port2a/DISKBOOT.BIN` (`118,001` B) matches P4 and decodes bit-for-bit to `candidate_loader.bin` (`118,000` B) `[VERIFIED: docs/PORT19_DISKBOOT_ENCODING.md:24-31, 367-369; tools/build_candidate_port2a.py:569-583]`. |
| P5 | Host build, validation, and preflight below exit `0` on the owner's host | Required; see 1.2. Verified in `docs/PORT19_GO_NOGO.md`. |
| P6 | Inspector witness address alignment (`0x0035F7A0`) | **RESOLVED (`VERIFIED`).** Candidate `boot_witness` is `0x0035F7A0` (Section `.data`, Type `D`, 32 B, 16-byte aligned) and `_end` is `0x00366CB0` `[VERIFIED: docs/PORT19_WITNESS_ADDRESS.md:17-20, 325-346; docs/PORT16_WITNESS_ADDRESS.md:15, 218]`. The candidate build outputs (`candidate_port2a/witness_inspector_metadata.json`, `candidate_port2a/witness_inspector_payload.bin`, `candidate_port2a/witness_inspector_gm110c.m`), the inspector builder/validator (`tools/build_witness_inspector.py:30, 37, 39, 42`, `tools/validate_witness_inspector.py:54, 73, 75, 78`), and the preflight tool (`tools/port18_trial_preflight.py:50, 488-567`) all pin and verify `0x0035F7A0`, default to `candidate_port2a/`, and reject the historical pre-correction `firmware/tools/` baseline fail-closed `[VERIFIED: docs/PORT19_WITNESS_ADDRESS.md:21-31, 60, 348-419]`. |

### 1.2 Host build, map generation, and validation commands

Run from the repository root on the host workstation. These steps only read and write host files.

```bash
# 1. Pinned toolchain present (toolchains/ is local and git-ignored, .gitignore:36)
toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-gcc --version

# 2. Deterministic platform source bootstrap (PORT-8A)
python3 -B tools/bootstrap_chdk_platform.py

# 3. Remove prior candidate artifacts to ensure clean rebuild
rm -rf candidate_port2a candidate_trace

# 4. Build candidate with tracing OFF (the default; unset G3X_TRACE, pass no --trace)
env -u G3X_TRACE python3 -B tools/build_candidate_port2a.py

# 5. Link core with map generation for layout inspection (docs/PORT17_TRACE_EVIDENCE.md:106-125)
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
cd ..

# 6. Validate the candidate (7 suites; also checks the OFF layout, see 1.3)
python3 -B tools/validate_candidate_port2a.py

# 7. Validate the candidate's witness inspector against the candidate ELF
#    (0x0035F7A0 = PORT-16/PORT-19 pinned boot_witness, docs/PORT19_WITNESS_ADDRESS.md:17-20, 325-332)
python3 -B tools/validate_witness_inspector.py \
  --elf candidate_port2a/candidate_main.elf \
  --payload-bin candidate_port2a/witness_inspector_payload.bin \
  --payload-elf candidate_port2a/witness_inspector_payload.o \
  --loader-script candidate_port2a/witness_inspector_gm110c.m \
  --metadata candidate_port2a/witness_inspector_metadata.json \
  --expected-addr 0x0035F7A0

# 8. Extract symbol table from candidate ELF for preflight verification
toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-nm \
  candidate_port2a/candidate_main.elf > candidate_port2a/candidate_symbols.txt

# 9. Preflight verification tool (PORT-18/PORT-19 preflight step with inspector inputs)
mkdir -p private/port18
python3 -B tools/port18_trial_preflight.py \
  candidate_port2a/DISKBOOT.BIN \
  candidate_port2a/candidate_symbols.txt \
  --inspector-metadata candidate_port2a/witness_inspector_metadata.json \
  --inspector-bin candidate_port2a/witness_inspector_payload.bin \
  --out private/port18/preflight_report.json
# The report's boot_witness, _end, inspector_metadata_witness, and inspector_payload_witness
# checks must all match 0x0035F7A0 / 0x00366CB0 (P6).
```

- **Toolchain**: the builder and both validators use `toolchains/gcc-arm-none-eabi-5_4-2016q3/bin` `[VERIFIED: tools/build_candidate_port2a.py:31-39; tools/validate_candidate_port2a.py:27-31; tools/validate_witness_inspector.py:80-83]`. Expected version string "5.4.1 20160919" `[VERIFIED: docs/PORT16_CANDIDATE_BUILD.md:87]`. The toolchain directory is git-ignored and must exist locally `[VERIFIED: .gitignore:36]`.
- **Bootstrap**: `tools/bootstrap_chdk_platform.py` recreates the platform/g3x source set from vendored baselines and is fail-closed `[VERIFIED: tools/bootstrap_chdk_platform.py:2-11]`. It was run before the PORT-16 build `[VERIFIED: docs/PORT16_CANDIDATE_BUILD.md:109]`.
- **Builder**: output goes to `candidate_port2a/` unless `--out-dir` is given or tracing is on `[VERIFIED: tools/build_candidate_port2a.py:43, 62, 1003-1006]`. It links the core at `0x3489b4` and the loader at `0x8000` `[VERIFIED: tools/build_candidate_port2a.py:424, 536]`, fails if `boot_witness` is not `0x0035F7A0` `[VERIFIED: tools/build_candidate_port2a.py:54, 147-153, 460]`, writes encoded `candidate_port2a/DISKBOOT.BIN` (`118,001` B, dancingbits row 13, byte 0 = `0x00`) `[VERIFIED: tools/build_candidate_port2a.py:569-583; docs/PORT19_DISKBOOT_ENCODING.md:24-31]`, the inspector `.o`, `.bin`, `.m` and metadata `[VERIFIED: tools/build_candidate_port2a.py:802-805]`, and the manifest `[VERIFIED: tools/build_candidate_port2a.py:896]`. Any failing sub-command exits non-zero `[VERIFIED: tools/build_candidate_port2a.py:172-175]`. The PORT-16 build exited `0` `[VERIFIED: docs/PORT16_CANDIDATE_BUILD.md:21, 118]`.
- **Map Generation (step 5)**: The builder's link command at `tools/build_candidate_port2a.py:419-440` has no map-output flag `[VERIFIED: tools/build_candidate_port2a.py:419-440]`. Step 5 executes the link command with map generation documented at `docs/PORT17_TRACE_EVIDENCE.md:106-125` quoted exactly, generating `candidate_port2a/candidate_main.map` for layout inspection `[VERIFIED: docs/PORT17_TRACE_EVIDENCE.md:106-125, 128]`.
- **Candidate validator**: runs 7 suites `[VERIFIED: tools/validate_candidate_port2a.py:576-582]` and exits `0` only if all pass `[VERIFIED: tools/validate_candidate_port2a.py:584-594]`. The PORT-16 run exited `0` `[VERIFIED: docs/PORT16_CANDIDATE_BUILD.md:22, 150]`.
- **Inspector validator (step 7)**: `tools/validate_witness_inspector.py` defaults to `candidate_port2a/` artifacts and expected address `0x0035F7A0` `[VERIFIED: tools/validate_witness_inspector.py:54, 73-79, 658-667; docs/PORT19_WITNESS_ADDRESS.md:21-23, 388-399]`. Passing explicit `--elf`, `--payload-bin`, `--payload-elf`, `--loader-script`, `--metadata`, and `--expected-addr 0x0035F7A0` flags (`tools/validate_witness_inspector.py:658-667`) makes the host invocation explicit `[INFERRED]`. It exits `0` only on success `[VERIFIED: tools/validate_witness_inspector.py:682-690]`.
- **Preflight verification (step 9)**: `tools/port18_trial_preflight.py` parses `boot_witness` (`0x0035F7A0`) and `_end` (`0x00366CB0`) against the pinned PORT-16/PORT-19 values `[VERIFIED: tools/port18_trial_preflight.py:50, 60-62, 469-471; docs/PORT19_WITNESS_ADDRESS.md:24-31, 401-419]`, verifies compile-time trace option is OFF (`TRACE_FORBIDDEN_SYMBOLS`) `[VERIFIED: tools/port18_trial_preflight.py:83-92, 462-481]`, verifies inspector metadata and payload binary witness address alignment (`0x0035F7A0`) when `--inspector-metadata` and `--inspector-bin` are passed `[VERIFIED: tools/port18_trial_preflight.py:488-567; docs/PORT19_WITNESS_ADDRESS.md:24-31]`, computes candidate SHA-256 and byte size `[VERIFIED: tools/port18_trial_preflight.py:449-453]`, enforces Phase 0 path safety (`PRIMARY.*`, `firmware/dumps/`, and stale `firmware/tools/` baseline rejected) `[VERIFIED: tools/port18_trial_preflight.py:99-133, 429-442]`, writes a structured JSON report `[VERIFIED: tools/port18_trial_preflight.py:591-594]`, and exits `0` only on success `[VERIFIED: tools/port18_trial_preflight.py:611-612, 688, 702]`.
- **Do not run** `tests/test_validate_witness_inspector.py` or `tools/build_witness_inspector.py` `[VERIFIED: AGENTS.md:45-46]`.
- **Stop rule**: if any of steps 1-9 (or any check in Section 1.3) does not exit `0`, stop and do not prepare a card `[INFERRED: docs/SAFETY.md:7-8]`.

### 1.3 Confirming tracing is OFF and inspecting link map

What is VERIFIED from tracked code:

- `G3X_TRACE` defaults to `0` `[VERIFIED: chdk-port/platform/g3x/sub/110c/g3x_trace.h:104-112]`.
- The builder enables tracing only with `--trace` or `G3X_TRACE` in `1/true/TRUE/yes/YES` `[VERIFIED: tools/build_candidate_port2a.py:998-1001]`. Step 4 unsets the variable and passes no `--trace`.
- With tracing off the builder does not add `-DG3X_TRACE=1` `[VERIFIED: tools/build_candidate_port2a.py:237-238]`, does not compile or archive `g3x_trace.c` `[VERIFIED: tools/build_candidate_port2a.py:248-300, 323-324]`, and links with `tools/link-boot.ld` (`chdk-port/tools/link-boot.ld`) instead of generating the trace link script `[VERIFIED: tools/build_candidate_port2a.py:353-354, 415-417]`.
- With `G3X_TRACE` off, `boot()` branches to `sub_fc05b3c8_my` and the trace block is compiled out `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:156-160, 441-487]`.
- The manifest status is `OFFLINE_CANDIDATE_BUILT` when tracing is off, and the `g3x_trace_enabled` key is written only when it is on `[VERIFIED: tools/build_candidate_port2a.py:914, 928, 932-935]`. The validator asserts that status `[VERIFIED: tools/validate_candidate_port2a.py:543]`.

What stays INFERRED, and which host commands do the remaining checks:

- `docs/PORT17_TRACE_EVIDENCE.md` labels "tracing OFF leaves `boot_witness = 0x0035F7A0` and `_end = 0x00366CB0` unchanged" as **INFERRED** and lists three checks: (1) the whole `.g3x_trace` stanza absent when OFF, (2) compare `boot_witness` and `_end` in the OFF link against the PORT-16 values, (3) pass `candidate_validate` `[VERIFIED: docs/PORT17_TRACE_EVIDENCE.md:232-235, 459, 492]`. This plan keeps that label: **OFF-layout preservation is INFERRED until the owner's own checks pass; do NOT present that passage as a completed verification.**
- **Prerequisite existence check**: The host must check that both `candidate_port2a/candidate_main.elf` and `candidate_port2a/candidate_main.map` exist and were produced by steps 4 and 5 before inspecting layout or recording measurements `[INFERRED]`.
- **Check (1) — Linker-stanza and map absence check**: `tools/port18_trial_preflight.py` checks `TRACE_FORBIDDEN_SYMBOLS` `[VERIFIED: tools/port18_trial_preflight.py:83-92]` and the owner scans `nm` symbol names, but an `nm` symbol listing cannot detect retained section statements, `ALIGN`, location-counter assignments (`. = ...`), or `KEEP` directives. `docs/PORT17_TRACE_EVIDENCE.md:232-234` requires their complete absence because they can move the layout without adding trace symbols `[VERIFIED: docs/PORT17_TRACE_EVIDENCE.md:232-234]`. Therefore, the owner or host must explicitly inspect the actual OFF linker script (`chdk-port/tools/link-boot.ld`) and the link map (`candidate_port2a/candidate_main.map`, uncommitted local file, `docs/PORT17_TRACE_EVIDENCE.md:128`) for those constructs. This check remains **PENDING / INFERRED** until the owner or host completes that inspection.
- **Check (2) — Address comparison**: The host must check that `boot_witness` and `_end` match the pinned values in both the ELF and link map before recording any measurements: step 6 (`tools/validate_candidate_port2a.py`) asserts `_start = 0x003489B4`, `boot_witness = 0x0035F7A0`, and `_end = 0x00366CB0` `[VERIFIED: tools/validate_candidate_port2a.py:50-52, 251-255, 311-326, 334]`, and preflight (step 9) checks `boot_witness = 0x0035F7A0` and `_end = 0x00366CB0` `[VERIFIED: tools/port18_trial_preflight.py:50, 60-62, 469-471]`. In `candidate_port2a/candidate_main.map`, the owner inspects the exact addresses of `boot_witness` and `_end` `[INFERRED: docs/PORT17_TRACE_EVIDENCE.md:234]`.
- **Check (3) — Candidate validator**: step 6 itself (`tools/validate_candidate_port2a.py`), which executes all 7 test suites fail-closed `[VERIFIED: tools/validate_candidate_port2a.py:576-594; docs/PORT17_TRACE_EVIDENCE.md:235]`.

Owner commands (host only):

```bash
# Verify ELF and map existence
test -f candidate_port2a/candidate_main.elf || { echo "ERROR: candidate_main.elf missing"; exit 1; }
test -f candidate_port2a/candidate_main.map || { echo "ERROR: candidate_main.map missing"; exit 1; }

# Manifest and trace symbols checks (every command exits 0 when tracing is OFF)
grep -n '"status"' candidate_port2a/candidate_manifest.json          # expect OFFLINE_CANDIDATE_BUILT
test -r candidate_port2a/candidate_manifest.json && ! grep -q -- 'g3x_trace_enabled' candidate_port2a/candidate_manifest.json && echo "OK: g3x_trace_enabled absent in candidate_port2a/candidate_manifest.json" || { echo "FAIL: g3x_trace_enabled present or read error in candidate_port2a/candidate_manifest.json"; false; }
test -r candidate_port2a/candidate_main.elf && toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-nm candidate_port2a/candidate_main.elf >/dev/null && ! toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-nm candidate_port2a/candidate_main.elf | grep -q -i -- 'g3x_trace' && echo "OK: g3x_trace absent in candidate_port2a/candidate_main.elf" || { echo "FAIL: g3x_trace present or read error in candidate_port2a/candidate_main.elf"; false; }
test ! -e candidate_trace/DISKBOOT.BIN && echo "OK: candidate_trace/DISKBOOT.BIN absent" || { echo "FAIL: candidate_trace/ exists: do NOT use it"; false; }

# Check (1) explicit inspection: verify no trace stanzas, ALIGN, or KEEP in OFF linker script and map
test -r chdk-port/tools/link-boot.ld && ! grep -q -E -- '(g3x_trace|KEEP)' chdk-port/tools/link-boot.ld && echo "OK: (g3x_trace|KEEP) absent in chdk-port/tools/link-boot.ld" || { echo "FAIL: (g3x_trace|KEEP) present or read error in chdk-port/tools/link-boot.ld"; false; }
test -r candidate_port2a/candidate_main.map && ! grep -q -i -- 'g3x_trace' candidate_port2a/candidate_main.map && echo "OK: g3x_trace absent in candidate_port2a/candidate_main.map" || { echo "FAIL: g3x_trace present or read error in candidate_port2a/candidate_main.map"; false; }

# Check (2) address comparison in map: boot_witness = 0x0035F7A0, _end = 0x00366CB0
grep -E '(boot_witness|_end$)' candidate_port2a/candidate_main.map
```

Expected results are `[INFERRED: tools/build_candidate_port2a.py:237-238, 323-324, 914, 932-935; docs/PORT17_TRACE_EVIDENCE.md:232-235]`: every command above exits `0` on a valid tracing-OFF candidate (printing `OK:` for each trace-absence check); if any command exits non-zero or prints `FAIL:`, stop immediately and do not prepare a card `[INFERRED: docs/SAFETY.md:7-8]`. A trace build is marked NOT trial-ready by the builder `[VERIFIED: tools/build_candidate_port2a.py:1014-1017; chdk-port/platform/g3x/sub/110c/g3x_trace.h:21-23]` and must never go on a card.

### 1.4 Candidate SHA-256 and size (recorded locally, never committed)

The host must verify that the link map and ELF exist, that layout inspection passes, and that `boot_witness` and `_end` match the pinned values, before recording any measurements `[INFERRED]`. Layout preservation stays `INFERRED`.

The candidate's SHA-256 digest and decimal byte size are computed directly during preflight (step 9), and can also be checked on the host with standard utilities:

```bash
sha256sum candidate_port2a/DISKBOOT.BIN
stat -c %s candidate_port2a/DISKBOOT.BIN

# Record both in an owner-local, git-ignored location
mkdir -p private/port18
{ sha256sum candidate_port2a/DISKBOOT.BIN; stat -c 'size %s' candidate_port2a/DISKBOOT.BIN; } \
  > private/port18/candidate_measurements.txt
```

- `private/` is git-ignored `[VERIFIED: .gitignore:34]`. `*.bin` is git-ignored `[VERIFIED: .gitignore:9]`. `.gitignore` has no rule for the other `candidate_port2a/` files (`.elf`, `.json`, `.m`) `[VERIFIED: .gitignore:1-71]`, so the owner must never stage `candidate_port2a/`, `candidate_trace/` or `private/` `[INFERRED: AGENTS.md:14; docs/SAFETY.md:5-6]`. Before and after the trial, `git status --short` must show none of them staged `[INFERRED]`.
- The measured SHA-256 and size are written only to `private/port18/` and to the owner's local copy of the Section 6 report (the PORT-19 GO/NO-GO decision record `docs/PORT19_GO_NOGO.md` records the verified reference SHA-256 and size as text only). This trial plan uses placeholders only.
- This document holds no real hash or byte count for the candidate. It uses only the placeholders `<sha256-recorded-locally>` and `<size-bytes>`. The real values exist on the owner's host in `private/port18/candidate_measurements.txt` and in the preflight JSON `private/port18/preflight_report.json` (step 9), and must match the reference values in `docs/PORT19_GO_NOGO.md`.
- **Compare before the trial**: the `sha256sum`/`stat` output and the SHA-256 and size in the preflight JSON must agree with each other. They must also agree with the PORT-16 reference `DISKBOOT.BIN` row in `docs/PORT16_CANDIDATE_BUILD.md:362` and `docs/PORT19_GO_NOGO.md`, which `chdk-port/platform/g3x/sub/110c/g3x_trace.h:12-14` says a tracing-OFF build matches byte for byte `[VERIFIED that both lines state a reference; values deliberately not reproduced here]`. Any mismatch means stop, do not prepare a card, and report `[INFERRED: docs/SAFETY.md:7-8]`.

### 1.5 Hardware preconditions (owner checks)

- [ ] P1 and P2 owner items verified and recorded by the human owner; P3, P4, and P6 are `VERIFIED`-resolved in PORT-19 (`docs/PORT19_BOOTDISK_VBR.md:13-34`, `docs/PORT19_DISKBOOT_ENCODING.md:13-31`, `docs/PORT19_WITNESS_ADDRESS.md:15-31`), and P5 host build/validation/preflight exits `0` (`docs/PORT19_GO_NOGO.md`).
- [ ] Camera is a PowerShot G3 X with internal build `GM1.10C` (P2).
- [ ] Reliable power: a fully charged battery `[VERIFIED requirement: docs/SAFETY.md:7]`. The battery model (NB-10L) and charge method are `[INFERRED]`.
- [ ] Dedicated spare card with no personal data `[INFERRED: docs/SAFETY.md:6-7]`.
- [ ] Card write-protect tab present and working `[INFERRED: docs/HANDOFF.md:923]`.

---

## 2. Card preparation

Do this on the host only after P1 and P2 are verified by the owner and P5 host checks pass (P3, P4, and P6 are `VERIFIED`-resolved in PORT-19). Nothing here is performed by an agent.

### 2.1 Filesystem

1. Use a **FAT16** or **FAT32** partition (or FAT12 on tiny media) `[VERIFIED: docs/PORT19_BOOTDISK_VBR.md:20-34; docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:47, 69]`. **exFAT is `UNSUPPORTED` (`VERIFIED`)**: the GM1.10C `Mounter.c` VBR routine (`0xFC37A556-0xFC37A55C`) bypasses both the `BOOTDISK` and `SCRIPT` VBR checks on exFAT (`Filesystem type = 4` at `0xFC37A556`, `b.n 0xfc37a67e` at `0xFC37A55C`), leaving `is_bootdisk = 0` and `is_scriptdisk = 0` `[VERIFIED: docs/PORT19_BOOTDISK_VBR.md:24, 33, 73-74, 138-155]`. Do **not** format the trial card as exFAT.
2. Card capacity: the Canon Basic source docs give no SDHC-only ceiling `[VERIFIED: docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:69]`. A prior test plan specified a primary FAT32 partition of ≤ 32 GB `[VERIFIED: docs/HANDOFF.md:1833]`. Using ≤ 32 GB is `[INFERRED: docs/HANDOFF.md:1833]`. The earlier failed `GM1.10C` Canon Basic attempt used a 64 GB SDXC card `[VERIFIED: docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:19, 24]`.
3. Partition table: an MBR with a FAT32 partition was used in the recorded attempt `[VERIFIED: docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:19]`. Whether the MBR active/bootable flag matters is `[UNKNOWN]`. Partition geometry, format provenance and in-camera formatting effects are `[UNKNOWN: docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:40, 75]`.

### 2.2 VBR markers (both in the FAT partition's volume boot sector, not the MBR)

- `BOOTDISK` (8 ASCII bytes, `42 4F 4F 54 44 49 53 4B`):
  * **On FAT32**: write `"BOOTDISK"` at VBR offset **`0x1E0`** (`480` decimal) `[VERIFIED: docs/PORT19_BOOTDISK_VBR.md:23, 67-69, 164-174]`.
  * **On FAT12 / FAT16**: write `"BOOTDISK"` at VBR offset **`0x40`** (`64` decimal) `[VERIFIED: docs/PORT19_BOOTDISK_VBR.md:22, 25, 70-72, 179-192]`.
  * **On exFAT**: `UNSUPPORTED` — do not use exFAT `[VERIFIED: docs/PORT19_BOOTDISK_VBR.md:24, 73-74, 138-155]`.
- `SCRIPT` (6 ASCII bytes, `53 43 52 49 50 54`) at VBR offset **`0x1F0`** (`496` decimal) on **FAT12, FAT16, and FAT32** `[VERIFIED: docs/PORT19_BOOTDISK_VBR.md:31-34, 69-72, 208-222; docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:48, 69]`.
- Spatial non-overlap and coexistence: on FAT32, `"BOOTDISK"` occupies `0x1E0..0x1E7` (8 bytes) and `"SCRIPT"` occupies `0x1F0..0x1F5` (6 bytes) with an 8-byte gap (`0x1E8..0x1EF`); on FAT12/FAT16, `"BOOTDISK"` occupies `0x40..0x47` and `"SCRIPT"` occupies `0x1F0..0x1F5` with a 424-byte gap; the `Mounter.c` VBR routine (`0xFC37A4B6-0xFC37A67E`) evaluates `is_bootdisk` and `is_scriptdisk` sequentially and independently `[VERIFIED: docs/PORT19_BOOTDISK_VBR.md:80-106, 123-222; docs/PROJECT_STATE.md:201, 209]`. Physical dual coexistence remains unverified on hardware `[VERIFIED: docs/PROJECT_STATE.md:201 "Dual Coexistence UNVERIFIED on hardware"]` and not ROM-closable `[VERIFIED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:468-470]`.

### 2.3 Files in the card root

| Name on card | Source on host | Basis |
|---|---|---|
| `DISKBOOT.BIN` | `candidate_port2a/DISKBOOT.BIN` | Must be the **ENCODED** file (dancingbits row 13 `[6, 5, 3, 7, 0, 2, 4, 1]`, byte 0 = `0x00`, `118,001` bytes) produced by `tools/build_candidate_port2a.py` `[VERIFIED: docs/PORT19_DISKBOOT_ENCODING.md:14-31, 271-296, 367-369; tools/build_candidate_port2a.py:569-583]`. Do **not** copy `candidate_loader.bin` (`118,000` bytes raw): GM1.10C `StartDiskboot` (`0xFC05BBEA` → `0xFC05BC3C` → `0xFC54DE38`) opens `"A/DISKBOOT.BIN"` (`0xFC05BC90`), requires byte 0 == `0x00` (`0xFC54DE3A-0xFC54DE3C`), and decodes `file_size - 1` bytes in-place via `0xFC42189C` before copying to `0x40008000` and branching to `0x8001` `[VERIFIED: docs/PORT19_DISKBOOT_ENCODING.md:17-22, 114-151, 153-323]`. |
| `extend.m` | `candidate_port2a/witness_inspector_gm110c.m`, renamed | Canon Basic runs root `extend.m` `[VERIFIED: docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:50]`. Generated by `tools/build_candidate_port2a.py` targeting `boot_witness` at `0x0035F7A0` `[VERIFIED: docs/PORT19_WITNESS_ADDRESS.md:17-20, 348-366; tools/build_candidate_port2a.py:804, 825]`. |
| `WITNESS.BIN` | `candidate_port2a/witness_inspector_payload.bin` | The script opens `A/WITNESS.BIN` `[VERIFIED: firmware/tools/witness_inspector_gm110c.m:100]` and requires exactly 444 bytes `[VERIFIED: firmware/tools/witness_inspector_gm110c.m:26, 109-116]`. Encodes `boot_witness = 0x0035F7A0` (`movw r7, #0xf7a0` / `movt r7, #0x0035` at offsets `0x0A`/`0x0E`) `[VERIFIED: docs/PORT19_WITNESS_ADDRESS.md:20, 355-366]`. Do **not** use `firmware/tools/` artifacts `[VERIFIED: docs/PORT19_WITNESS_ADDRESS.md:60]`. `A/` = card root is `[INFERRED]`. |
| `script.req` | created on host | Root file containing only `for DC_scriptdisk` (17 bytes) `[VERIFIED: docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:20, 49]`. |

```bash
printf 'for DC_scriptdisk' > /path/to/card/script.req   # 17 bytes
```

Compare each copied file with its host source using `cmp` before unmounting `[INFERRED]`. Do not put any `TRACE.LOG` on the card; if one is already there, delete it or use a freshly formatted card, so that any `TRACE.LOG` found later is not a leftover `[INFERRED]`.

### 2.4 Unmount and lock

1. `sync`, then unmount cleanly `[INFERRED]`.
2. Slide the write-protect tab to **LOCKED**. Tracked ROM notes say the SD write-protect switch "MUST be LOCKED" for SD boot, checked at `0xFC05BC04` `[VERIFIED: docs/PORT19_DISKBOOT_ENCODING.md:89-93; docs/HANDOFF.md:923; docs/PROJECT_STATE.md:333; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:32]`. A locked tab may also stop any on-camera writes to the card `[INFERRED: docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:76]`.

---

## 3. Trial procedure

The owner performs every step by hand, in one powered session, and only after P1 and P2 are verified by the owner and P5 host checks pass (P3, P4, and P6 are `VERIFIED`-resolved in PORT-19). Doing it in one session is required because the witness lives in volatile RAM `[INFERRED: firmware/tools/witness_inspector_gm110c.m:14, 185-188]`.

**Step 1 — Insert.** Camera off. Insert the charged battery and the LOCKED card. Close the door `[INFERRED]`.

**Step 2 — Power on in Playback.** Power on the camera by pressing the Playback button to start in Playback mode `[VERIFIED: docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:51; docs/PORT16_OWNER_TRIAL_PLAN.md:153]`. Start a stopwatch. Note the LCD, sounds, and lens movement. The lens remains safely retracted in Playback mode `[INFERRED: docs/PORT16_OWNER_TRIAL_PLAN.md:169]`.

The intended internal sequence (for interpreting outcomes only; none of it is observable directly):

- `task_Startup` (`0xFC05B8FC`) calls `StartDiskboot` (`0xFC05BBEA`) `[VERIFIED: docs/PORT19_DISKBOOT_ENCODING.md:77-83; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:30; docs/HANDOFF.md:921]`, which checks the write-protect switch at `0xFC05BC04` and the `BOOTDISK` VBR signature (`0x1E0` on FAT32, `0x40` on FAT12/FAT16) via `0xFC37AEA6` → `0xFC37A4B6` → `0xFC37B2AE` `[VERIFIED: docs/PORT19_BOOTDISK_VBR.md:164-206, 250-259; docs/PORT19_DISKBOOT_ENCODING.md:89-101; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:32-33]`.
- `sub_fc05bc3c` (`0xFC05BC3C`) opens `"A/DISKBOOT.BIN"`, reads it into buffer `r4`, calls `sub_fc54de38` (`0xFC54DE38`) to verify leading byte `0x00`, shift left by 1 byte, and decode `file_size - 1` bytes in-place via `sub_fc42189c` (`0xFC42189C`, DancingBits Row 13 at `0xFC7C0F8C`), then calls `sub_fc0d9c9c` (`0xFC0D9C9C` → `0xFC0007C0`) to copy the decoded payload to `0x40008000` (aliased to `0x00008000`) and branch via `bx ip` with `ip = r7 = 0x8001` (Thumb state, `pc = 0x00008000`, privileged mode, IRQs disabled, `lr = 0xFC05BC7F` returning to `0xFC05BC7E`) `[VERIFIED: docs/PORT19_DISKBOOT_ENCODING.md:109-323; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:71, 77-82]`.
- Candidate loader executes `my_restart()` and copies the core payload to `0x003489B4` `[VERIFIED that it is stated: docs/PORT16_OWNER_TRIAL_PLAN.md:158; core destination value: tools/build_candidate_port2a.py:940; tools/validate_candidate_port2a.py:50]` (the loader source the PORT-16 plan cites is untracked, so the copy behaviour itself is `[INFERRED]`), then records **Stage 1 (LOADER_REACHED = `0x01`)** `[VERIFIED mask: chdk-port/platform/g3x/sub/110c/boot_witness.h:13; firmware/tools/witness_inspector_payload.S:12; tools/validate_witness_inspector.py:264-265; docs/HANDOFF.md:428; docs/PROJECT_STATE.md:200]` into `boot_witness` at **`0x0035F7A0`** `[VERIFIED address: docs/PORT19_WITNESS_ADDRESS.md:17-20, 325-332; docs/PORT16_WITNESS_ADDRESS.md:15; docs/PORT16_CANDIDATE_BUILD.md:23; tools/build_candidate_port2a.py:54; tools/validate_candidate_port2a.py:48; tools/port18_trial_preflight.py:50]`, synchronizes L1 caches via DCCISW/ICIALLU, enforces disabled interrupts (`cpsid if`), and branches to core entry `0x003489B5` `[VERIFIED entry: chdk-port/platform/g3x/sub/110c/boot_witness.h:27; tools/build_candidate_port2a.py:941; tools/validate_witness_inspector.py:269; instructions: tools/validate_candidate_port2a.py:438-441]`.
- Candidate core executes `boot()`, zeroes Canon BSS strictly up to `0x003489B4`, and branches to `sub_fc05b3c8_my` `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:144-161; tools/build_candidate_port2a.py:940]`.
- `sub_fc05b3c8_my()` records **Stage 2 (CORE_REACHED = `0x03`)** `[VERIFIED mask value: chdk-port/platform/g3x/sub/110c/boot_witness.h:25; firmware/tools/witness_inspector_payload.S:13; assignment (STAGE_LOADER | STAGE_CORE): chdk-port/platform/g3x/sub/110c/boot_prototype.c:39; tools/validate_witness_inspector.py:266-267; docs/HANDOFF.md:428; docs/PROJECT_STATE.md:200]` into `boot_witness` at `0x0035F7A0` `[VERIFIED address: docs/PORT19_WITNESS_ADDRESS.md:17-20; docs/PORT16_WITNESS_ADDRESS.md:15; docs/PORT16_CANDIDATE_BUILD.md:23]`, shifts the DryOS heap base to `new_sa = &_end` (**`0x00366CB0`**) `[VERIFIED address: docs/PORT19_WITNESS_ADDRESS.md:332; docs/PORT16_WITNESS_ADDRESS.md:218; docs/PORT16_CANDIDATE_BUILD.md:24; tools/build_candidate_port2a.py:891; tools/validate_candidate_port2a.py:52; tools/port18_trial_preflight.py:61; assignment: chdk-port/platform/g3x/sub/110c/boot_prototype.c:24, 172-174]`, and dispatches into DryOS kernel initialization.
- DryOS initial task spawns `task_Startup_my()`, initializes camera drivers, spawns `SD1stInit` via `sub_fc31b1f4`, omits `StartDiskboot` to prevent bootloop `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:391-401]`, records **Stage 3 (CONTINUATION_ATTEMPTED = `0x07`)** `[VERIFIED mask value: chdk-port/platform/g3x/sub/110c/boot_witness.h:16, 25; firmware/tools/witness_inspector_payload.S:14; assignment (STAGE_LOADER | STAGE_CORE | STAGE_CONTINUATION): chdk-port/platform/g3x/sub/110c/boot_prototype.c:52; tools/validate_witness_inspector.py:268-271; docs/HANDOFF.md:428; docs/PROJECT_STATE.md:200]` into `boot_witness` at `0x0035F7A0` `[VERIFIED address: docs/PORT19_WITNESS_ADDRESS.md:17-20; docs/PORT16_WITNESS_ADDRESS.md:15; docs/PORT16_CANDIDATE_BUILD.md:23]`, and executes terminal branch `b.w sub_fc0d0126` to continue stock Canon firmware boot `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:433-438; tools/build_candidate_port2a.py:950]`.
- Note on visual observability: `boot_prototype.c` contains **NO** screen drawing routines, LCDMsg calls or LED blinking sequences `[VERIFIED: docs/PORT16_OWNER_TRIAL_PLAN.md:165; chdk-port/platform/g3x/sub/110c/boot_prototype.c:1-487]`. The candidate boot binary provides no direct visual output.

**Step 3 — Observe stock Playback screen.** Look for the Canon Playback UI (photo display or "No images") `[VERIFIED: docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:23, 51; docs/PORT16_OWNER_TRIAL_PLAN.md:168]`. If the camera hangs, goes black or restarts, go straight to Section 5 `[INFERRED: docs/SAFETY.md:7]`.

**Step 4 — Activate Canon Basic inspector in Playback mode.** While the camera remains powered in Playback mode, press the center **`FUNC./SET`** button once `[VERIFIED: docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:51-52; docs/PORT16_OWNER_TRIAL_PLAN.md:175]`. Canon Basic detects `script.req` and the VBR `SCRIPT` marker, parses `extend.m` (`candidate_port2a/witness_inspector_gm110c.m`), allocates memory, loads `A/WITNESS.BIN` (444 B, `candidate_port2a/witness_inspector_payload.bin`), synchronizes L1 Harvard caches, invokes the native inspector payload at `buf + 1`, reads and evaluates `boot_witness` at `0x0035F7A0` `[VERIFIED address: docs/PORT19_WITNESS_ADDRESS.md:17-20, 348-366; docs/PORT16_CANDIDATE_BUILD.md:311, 337, 432; tools/build_candidate_port2a.py:54; tools/port18_trial_preflight.py:50]`, registers two OSD message handles (`h_title` and `h_status`), and finishes non-blocking `[VERIFIED: firmware/tools/witness_inspector_gm110c.m:8-16, 52-84, 90-189]`. Do not press `FUNC./SET` repeatedly, as `extend.m` can generally be started only once per boot `[VERIFIED: docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:53]`.

**Step 5 — Hand-switch to Shooting mode (Live View) without restarting.** Immediately after pressing `FUNC./SET`, switch the camera by hand from Playback mode to Shooting mode (Live View) without powering off or restarting the camera (e.g. press the shutter button half-way or press the Playback/Shooting button) `[INFERRED: docs/PORT16_OWNER_TRIAL_PLAN.md:177-180; firmware/tools/witness_inspector_gm110c.m:185-188]`. Switching via the mode dial is `[UNKNOWN]` in effectiveness and not recommended.
*Technical rationale*: The inspector script specifies:
*"Message descriptors are intentionally retained in firmware RAM for Live View inspection in Shooting mode. Total dynamic footprint is strictly bounded to 112 bytes (two 56-byte descriptors)"* `[VERIFIED source comment text: firmware/tools/witness_inspector_gm110c.m:185-188]`. That comment describes retained descriptors only. The expectation that the Playback UI may occlude the OSD messages and that the retained descriptors become visibly rendered after switching to Shooting mode (Live View) is `[INFERRED: firmware/tools/witness_inspector_gm110c.m:185-188; docs/PORT16_OWNER_TRIAL_PLAN.md:180]`.

**Step 6 — Observe and photograph two-line OSD readout on LCD.** In Live View, inspect the on-screen display for the two retained text lines:
- Line 1 (`h_title`, x=60, y=140): stage indicator string (e.g. `CONT_ATTEMPTED` in Yellow) `[VERIFIED definition: firmware/tools/witness_inspector_gm110c.m:8-12, 83]`.
- Line 2 (`h_status`, x=60, y=180): freshness indicator string (e.g. `FRESHNESS_UNVERIFIED` in Yellow) `[VERIFIED definition: firmware/tools/witness_inspector_gm110c.m:13-16, 84]`.
Take a clear digital photo of the LCD screen. If no readout is visible, note whether standard Live View UI appears without overlay `[INFERRED: docs/PORT16_OWNER_TRIAL_PLAN.md:185-192]`.

**Step 7 — Power off and remove card.** Power off normally if responsive; if unresponsive, pull the battery `[INFERRED]`. Remove the SD card and bring it to the host workstation for outcome evaluation `[INFERRED]`.

---

## 4. Outcome table

### 4.1 Outcome Table (O1 - O16)

Witness inspector: `candidate_port2a/witness_inspector_gm110c.m` (payload: `candidate_port2a/witness_inspector_payload.bin`, validator: `tools/validate_witness_inspector.py`; template source: `firmware/tools/witness_inspector_gm110c.m`).
Trace parser: `tools/port17_trace_parser.py`.

| ID | `camera_behaviour` | Witness Readout on LCD | `TRACE.LOG` on card | Meaning | Evidence & Classification | Next Host Action |
|:---:|---|---|:---:|---|---|---|
| **O1** | `normal_stock_boot` | Present: `CONT_ATTEMPTED` / `FRESHNESS_UNVERIFIED` (Yellow/Yellow) | no | Witness RAM holds stage `0x07` with core entry `0x003489B5` and an 8-aligned loader SP. This does **not** confirm boot success or that the record is from this attempt (INCONCLUSIVE). | `[VERIFIED: firmware/tools/witness_inspector_gm110c.m:8, 19-24; tools/validate_witness_inspector.py:268-271; chdk-port/platform/g3x/sub/110c/boot_witness.h:16, 25-27; tools/build_candidate_port2a.py:941]`; attribution `[UNKNOWN: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:476-477]` | Keep the photo. File `port18-report` with `O1`. Independent post-continuation evidence is still needed `[VERIFIED: firmware/tools/witness_inspector_gm110c.m:24]`; no tracked mechanism exists `[VERIFIED: docs/PORT16_OWNER_TRIAL_PLAN.md:234]`. |
| **O2** | `normal_stock_boot` | Present: `CORE_REACHED` / `FRESHNESS_UNVERIFIED` (White/Yellow) | no | Witness RAM holds stage `0x03`. Continuation was not recorded. INCONCLUSIVE attribution. | `[VERIFIED: firmware/tools/witness_inspector_gm110c.m:9, 14; tools/validate_witness_inspector.py:266-267; chdk-port/platform/g3x/sub/110c/boot_witness.h:14, 25; chdk-port/platform/g3x/sub/110c/boot_prototype.c:39]`; why Stage 3 is missing `[UNKNOWN]` | Keep the photo. Review `chdk-port/platform/g3x/sub/110c/boot_prototype.c:168-439` (core → `task_Startup_my`) offline. |
| **O3** | `normal_stock_boot` | Present: `LOADER_REACHED` / `FRESHNESS_UNVERIFIED` (White/Yellow) | no | Witness RAM holds stage `0x01`. Core stage not recorded. INCONCLUSIVE attribution. | `[VERIFIED: firmware/tools/witness_inspector_gm110c.m:10, 14; tools/validate_witness_inspector.py:264-265; chdk-port/platform/g3x/sub/110c/boot_witness.h:13, 25; firmware/tools/witness_inspector_payload.S:12]`; cause `[UNKNOWN]` | Keep the photo. Review the loader handoff checks (`tools/validate_candidate_port2a.py:400-444`) and `docs/PORT16_CANDIDATE_BUILD.md:165-167` offline. |
| **O4** | `normal_stock_boot` | Absent or unknown (no overlay) | no | Inconclusive. Possible causes: card not seen as script disk, `script.req`/`SCRIPT` marker problem, `FUNC./SET` did not start `extend.m`, `setup()` failed to get message handles (script exits silently), overlay hidden, or `DISKBOOT.BIN` not run at all (e.g. unlocked tab, wrong `BOOTDISK` offset for filesystem, or exFAT card). | `[INFERRED: docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:10, 12, 47-53; firmware/tools/witness_inspector_gm110c.m:52-81, 169-174; docs/PORT19_BOOTDISK_VBR.md:20-34; docs/HANDOFF.md:923]` | On the host, check the card: filesystem is FAT32 or FAT12/FAT16 (not exFAT), `BOOTDISK` at VBR `0x1E0` (FAT32) or `0x40` (FAT12/FAT16), `SCRIPT` at VBR `0x1F0`, `script.req` bytes, encoded `DISKBOOT.BIN` (`118,001` B, byte 0 = `0x00`), file names and sizes, lock tab. |
| **O5** | `normal_stock_boot` | Present (any readout) | yes | A `TRACE.LOG` exists, but the OFF candidate cannot write one. Its source and age are `UNKNOWN`. | `[VERIFIED: chdk-port/platform/g3x/sub/110c/g3x_trace.h:131-137; chdk-port/platform/g3x/sub/110c/g3x_trace.c:133-140; tools/build_candidate_port2a.py:248-300]`; origin `[UNKNOWN]` | Copy the file to the host. Run `python3 tools/port17_trace_parser.py <path> -H`. Record that parsing does not tie it to this trial. Map the witness readout as in O1-O3/O6/O7/O13 in `notes`. |
| **O6** | `normal_stock_boot` | Present: `WITNESS_INVALID` / `INVALID / CORRUPT` (Red/Red) | no | The payload read the witness and rejected it. The reference parser returns the same strings and colours for **all** of these causes: (a) buffer under 32 bytes; (b) bad magic (`magic != 0x5749544E`) or bad version (`version != 0x00010001`); (c) bad checksum (`checksum != expected_cs`); (d) invalid stage mask (`stage_state` not in `{1, 3, 7}`); (e) at Stage 3 (`stage_state == 7`), unexpected core entry address (`core_entry_pc != 0x003489B5`) or misaligned loader stack (`loader_sp % 8 != 0`). Header and checksum may be valid in cases (d) and (e). **The specific cause is `UNKNOWN` from the overlay alone.** | `[VERIFIED: tools/validate_witness_inspector.py:242-274; tools/validate_witness_inspector.py:85-86; firmware/tools/witness_inspector_gm110c.m:12, 16; chdk-port/platform/g3x/sub/110c/boot_witness.h:8-9, 13-16, 21-30]`; that the reference parser matches the on-camera payload `[INFERRED: tools/validate_witness_inspector.py:243]` | Keep the photo. On the host, rerun step 7 (`tools/validate_witness_inspector.py` with explicit candidate arguments) and read its full output to confirm that payload and script match the candidate. If a witness dump exists, decode its 8 words using `chdk-port/platform/g3x/sub/110c/boot_witness.h:21-30` against cases (a)-(e). No tracked tool produces such a dump `[VERIFIED: docs/PORT16_OWNER_TRIAL_PLAN.md:199-200]`. |
| **O7** | `normal_stock_boot` | Present: `STALE / REPLAY` / `NONCE_MISMATCH` (Yellow/Yellow) | no | A non-zero, non-fixed `expected_nonce` did not match `session_nonce`. Not expected with the shipped script (`expected_nonce = 0`). | `[VERIFIED: tools/validate_witness_inspector.py:258-261; firmware/tools/witness_inspector_gm110c.m:11, 15, 28]` | Keep the photo. Compare the `extend.m` on the card with `candidate_port2a/witness_inspector_gm110c.m` byte for byte (`cmp`). |
| **O8** | `hang` | Any | no | Freeze, black screen or no response after power-on. Cause `UNKNOWN`. Tracked candidates include the halt loops in `boot_prototype.c` or an unhandled fault during early boot/continuation. | `[INFERRED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:183-190, 349-354; docs/HANDOFF.md:987]`; cause `[UNKNOWN]` | Recovery 5.1. Record the time to hang and the screen state. Do not retry before root-cause review. |
| **O9** | `hang` | Any | yes | Hang as in O8, plus a `TRACE.LOG` of `UNKNOWN` origin (see O5). | `[INFERRED: as O8 and O5]` | Recovery 5.1. Parse `TRACE.LOG` on the host with `tools/port17_trace_parser.py <path> -H`; record that it is not tied to this attempt. |
| **O10** | `no_power_on` | Any | no | No LCD, no LED, no lens movement. Whether any code ran is `UNKNOWN`. Possible causes include a battery or door problem. | `[INFERRED: docs/SAFETY.md:7]`; cause `[UNKNOWN]` | Recovery 5.2. |
| **O11** | `abnormal_state` | Any | no | Restart loop, error message, lens error or erratic behaviour. Cause `UNKNOWN`. | `[INFERRED: docs/SAFETY.md:7; docs/PORT16_OWNER_TRIAL_PLAN.md:272-274]` | Recovery 5.3. Stop. Do not retry. |
| **O12** | `abnormal_state` | Any | yes | As O11, plus a `TRACE.LOG` of `UNKNOWN` origin. | `[INFERRED: as O11 and O5]` | Recovery 5.3. Parse `TRACE.LOG` on the host with `tools/port17_trace_parser.py <path> -H`. Stop. |
| **O13** | `normal_stock_boot` | Present: script error, White/White (`PORT-1G: ERR_COMPAT`, `ERR_ALLOC`, `ERR_OPEN`, `ERR_READ` or `ERR_CLOSE`) | no | `extend.m` ran but stopped before or around the payload: firmware mismatch, allocation failure, `WITNESS.BIN` not found, size ≠ 444 B, or close failure. | `[VERIFIED: firmware/tools/witness_inspector_gm110c.m:85-86, 95-122, 176-180]` | Keep the photo. On the host, check that `WITNESS.BIN` exists and is 444 B, and rerun step 7. `ERR_COMPAT` → recheck P2. |
| **O14** | `normal_stock_boot` | Absent or unknown | yes | As O4, plus a `TRACE.LOG` of `UNKNOWN` origin (see O5). | `[INFERRED: as O4 and O5]` | As O4. Parse `TRACE.LOG` on the host with `tools/port17_trace_parser.py <path> -H`. |
| **O15** | `no_power_on` | Any | yes | As O10, plus a `TRACE.LOG` found although tracing is OFF and card preparation (2.3) requires removing any existing log. This is an anomaly; its origin and age are `UNKNOWN` (whether any code ran is `UNKNOWN`, see O10). | `[INFERRED: as O10 and O5]`; origin and age `[UNKNOWN]` | Recovery 5.2. Keep the file unmodified. Record its SHA-256, size and timestamp locally (never committed). Run `python3 tools/port17_trace_parser.py <path> -H` on it. Record its provenance as `UNKNOWN`. |
| **O16** | `unclassifiable` | Any | Any | None of O1-O15 fits. | `[UNKNOWN]` | Power off (or pull the battery). Keep the card unmodified. Describe the behaviour in `notes`. Wait for human review. |

### 4.2 Decision Matrix for Report-to-Outcome Mapping

The PORT-18 report-ingest tool (`tools/port18_trial_report.py`) parses the report block and uses the decision matrix below to map every combination of report values (`camera_behaviour`, `witness_observed`, `trace_log_present`, and observed readout detail) to exactly one outcome identifier (`outcome_id`) `[VERIFIED: tools/port18_trial_report.py:830-1194]`:

| `camera_behaviour` | `witness_observed` | `trace_log_present` | On-screen readout / detail | `outcome_id` |
|---|---|---|---|:---:|
| `normal_stock_boot` | `yes` | `no` | Stage 3 (`CONT_ATTEMPTED` / `FRESHNESS_UNVERIFIED`, Yellow) | **`O1`** |
| `normal_stock_boot` | `yes` | `no` | Stage 2 (`CORE_REACHED` / `FRESHNESS_UNVERIFIED`, White/Yellow) | **`O2`** |
| `normal_stock_boot` | `yes` | `no` | Stage 1 (`LOADER_REACHED` / `FRESHNESS_UNVERIFIED`, White/Yellow) | **`O3`** |
| `normal_stock_boot` | `yes` | `no` | Witness Corrupt/Invalid (`WITNESS_INVALID` / `INVALID / CORRUPT`, Red) | **`O6`** |
| `normal_stock_boot` | `yes` | `no` | Nonce Mismatch (`STALE / REPLAY` / `NONCE_MISMATCH`, Yellow) | **`O7`** |
| `normal_stock_boot` | `yes` | `no` | Inspector Script Error (`PORT-1G: ERR_*`, White) | **`O13`** |
| `normal_stock_boot` | `no` | `no` | None (Standard Canon Playback UI only) | **`O4`** |
| `normal_stock_boot` | `unknown` | `no` | Unobserved / Unverified | **`O4`** |
| `normal_stock_boot` | `yes` | `yes` | Any witness readout observed | **`O5`** |
| `normal_stock_boot` | `no` | `yes` | None (Standard Canon Playback UI only) | **`O14`** |
| `normal_stock_boot` | `unknown` | `yes` | Unobserved / Unverified | **`O14`** |
| `hang` | `yes` | `no` | Any witness readout observed | **`O8`** |
| `hang` | `no` | `no` | None | **`O8`** |
| `hang` | `unknown` | `no` | Unknown / Unobserved | **`O8`** |
| `hang` | `yes` | `yes` | Any witness readout observed | **`O9`** |
| `hang` | `no` | `yes` | None | **`O9`** |
| `hang` | `unknown` | `yes` | Unknown / Unobserved | **`O9`** |
| `no_power_on` | `yes` | `no` | Any (Unlikely on hardware) | **`O10`** |
| `no_power_on` | `no` | `no` | None (Camera unpowered) | **`O10`** |
| `no_power_on` | `unknown` | `no` | Unknown (Camera unpowered) | **`O10`** |
| `no_power_on` | `yes` | `yes` | Any (Unlikely on hardware) | **`O15`** |
| `no_power_on` | `no` | `yes` | None (Camera unpowered) | **`O15`** |
| `no_power_on` | `unknown` | `yes` | Unknown (Camera unpowered) | **`O15`** |
| `abnormal_state` | `yes` | `no` | Any witness readout observed | **`O11`** |
| `abnormal_state` | `no` | `no` | None | **`O11`** |
| `abnormal_state` | `unknown` | `no` | Unknown / Unobserved | **`O11`** |
| `abnormal_state` | `yes` | `yes` | Any witness readout observed | **`O12`** |
| `abnormal_state` | `no` | `yes` | None | **`O12`** |
| `abnormal_state` | `unknown` | `yes` | Unknown / Unobserved | **`O12`** |
| `unclassifiable` | Any (`yes`/`no`/`unknown`) | Any (`yes`/`no`) | Any unclassifiable anomaly | **`O16`** |

---

## 5. Recovery plan

`docs/SAFETY.md:7` requires a known recovery path and rollback conditions before any hardware test `[VERIFIED]`. No physical recovery step below has been tested on this camera. Each step is labelled.

**Mechanisms that keep `DISKBOOT.BIN` from loading** (basis for returning to stock boot):

- R-a. **Unlock the card or remove it.** SD boot requires the write-protect switch to be LOCKED `[VERIFIED: docs/HANDOFF.md:923; docs/PROJECT_STATE.md:333]`. That an unlocked card or no card leads to a normal stock start is `[INFERRED: docs/HANDOFF.md:923; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:230-242]`.
- R-b. **No `BOOTDISK` marker.** SD boot requires the `BOOTDISK` VBR signature `[VERIFIED: docs/HANDOFF.md:923; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:33]`. That a card without it boots stock is `[INFERRED]`.
- R-c. When `StartDiskboot` loads nothing, it returns through `0xFC05BC38` → `0xFC05C4DE` (`bx lr`) and `task_Startup` continues at `0xFC05B912` `[VERIFIED: docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:230-239]`.
- R-d. The candidate runs only from RAM: the loader is linked at `0x8000` `[VERIFIED: tools/build_candidate_port2a.py:536]` and the core at `0x003489B4..0x00366CB0` `[VERIFIED: tools/validate_candidate_port2a.py:50-52; docs/PORT16_CANDIDATE_BUILD.md:23-24]`. `boot_prototype.c` writes no flash or `SetParameterData` call `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:1-487, by inspection]`. That a power cycle removes the candidate is `[INFERRED]`. Persistence risks (flash/EEPROM corruption by downstream code, mechanical damage, watchdog loops) are listed in `docs/PORT16_OWNER_TRIAL_PLAN.md:271-274` `[VERIFIED that they are listed]`. Their likelihood is `[UNKNOWN]`.

### 5.1 Hang (O8, O9)

1. Do not press buttons repeatedly `[INFERRED]`.
2. Open the battery door and remove the battery `[INFERRED: docs/PORT16_OWNER_TRIAL_PLAN.md:244-245]`.
3. Remove the card `[INFERRED: R-a]`.
4. Leave the camera without power for at least 30 s `[INFERRED]`.
5. Put the battery back with **no card**. Power on in Playback `[INFERRED: R-a; docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:51]`.
6. Confirm stock behaviour: normal Playback screen, then Shooting mode with live view and responsive menus `[INFERRED]`. If it is not normal, go to 5.3 step 5.
7. On the host, make the card safe before it goes near the camera again: unlock it (R-a), or rename `DISKBOOT.BIN`, or reformat `[INFERRED: R-a, R-b]`.

### 5.2 No boot / no power-on (O10, O15)

1. Remove the battery and the card `[INFERRED]`.
2. Check the battery's charge in the charger and recharge it `[INFERRED: docs/SAFETY.md:7 "reliable power"]`.
3. Check that the battery/card door latches `[INFERRED]`.
4. Insert the charged battery with **no card**, close the door and press Playback `[INFERRED: R-a]`.
5. If still dead: leave it without a battery for a longer period, then retry once with no card `[INFERRED]`. If it is still dead, stop and report. Further recovery is `[UNKNOWN]`.

### 5.3 Abnormal state (O11, O12, O16)

1. Remove the battery at once. Do not let a restart loop continue `[INFERRED]`.
2. Remove the card and keep it unmodified for host inspection `[INFERRED]`.
3. On the host, list the card contents. Parse any `TRACE.LOG` with `python3 tools/port17_trace_parser.py <path> -H` `[VERIFIED usage: tools/port17_trace_parser.py:784-795]`. Its origin is `[UNKNOWN]` (see O5).
4. Insert the battery with **no card** and power on in Playback `[INFERRED: R-a]`.
5. **Abort rule**: if stock behaviour does not return (lens error, black screen, error codes, restart loop), **stop, do not retry**, and report with Section 6 `[INFERRED: docs/SAFETY.md:7; docs/PORT16_OWNER_TRIAL_PLAN.md:266]`. Recovery beyond this point is `[UNKNOWN]`.

---

## 6. Results-report template

The owner fills out the structured report below following the physical trial attempt, manually compares `candidate_sha256` and `candidate_size` against the preflight output (`private/port18/preflight_report.json` / `private/port18/candidate_measurements.txt`) and `docs/PORT19_GO_NOGO.md`, and parses/validates the report with `tools/port18_trial_report.py` (`tools/port18_trial_report.py:1354-1469`). Keep the filled report in `private/port18/` (git-ignored, `.gitignore:34`); it contains the locally computed candidate hash and must not be committed to git.

### 6.1 Documentation of Allowed Values for Enumerated Keys

Every fixed key in the report template has a strictly defined set of allowed values:

- **`candidate_sha256`**: Exactly 64 lowercase hexadecimal characters representing the locally computed SHA-256 checksum of `candidate_port2a/DISKBOOT.BIN` (placeholder `<sha256-recorded-locally>`), or `none` if uncomputed. The real value is recorded only on the owner's host and must never be committed to git.
- **`candidate_size`**: Integer decimal byte count of `candidate_port2a/DISKBOOT.BIN` (placeholder `<size-bytes>`), or `0` if uncomputed. The real value is recorded only on the owner's host and must never be committed to git.
- **`trial_date`**: ISO 8601 calendar date format `YYYY-MM-DD` (e.g. `2026-10-31`).
- **`card_prepared`**:
  * `yes`: The SD card was formatted with an allowed filesystem per Section 2.1 (FAT32 or FAT12/FAT16; exFAT unsupported; format and bootable-flag requirements INFERRED/UNKNOWN), written with VBR markers `BOOTDISK` (`0x1E0` on FAT32, `0x40` on FAT12/FAT16) and `SCRIPT` (`0x1F0`) per Section 2.2 (`docs/PORT19_BOOTDISK_VBR.md:20-34`), populated with encoded `DISKBOOT.BIN` (`118,001` B, dancingbits row 13, byte 0 = `0x00`, `docs/PORT19_DISKBOOT_ENCODING.md:14-31`), `extend.m`, `WITNESS.BIN` (`0x0035F7A0`, `docs/PORT19_WITNESS_ADDRESS.md:17-20`), and `script.req`, and write-protect locked `[VERIFIED filenames and signatures: docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:20, 48-50; docs/PORT19_BOOTDISK_VBR.md:20-34; docs/PORT19_DISKBOOT_ENCODING.md:14-31; docs/PORT19_WITNESS_ADDRESS.md:17-20; filesystem requirements: docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:47, 69; docs/HANDOFF.md:1833]`.
  * `no`: Card preparation was skipped, incomplete, or failed.
- **`camera_behaviour`**:
  * `normal_stock_boot`: The camera powered on normally into factory Playback mode without crashing or hanging.
  * `hang`: The camera froze, displayed a black screen, or became unresponsive to controls.
  * `no_power_on`: The camera did not power on at all (no power LED, no display, no motor motion).
  * `abnormal_state`: The camera reboot-looped, displayed error codes on the display, or exhibited erratic hardware behaviour.
  * `unclassifiable`: Observed camera behaviour does not conform to any categorized state (e.g. partial screen garble, unexpected audio tones, or unlisted hardware state).
- **`witness_observed`**:
  * `yes`: A two-line text OSD readout from the witness inspector was visibly observed on the LCD screen in Live View.
  * `no`: No witness inspector text overlay was visible on the LCD screen (standard Canon UI or blank screen).
  * `unknown`: Visual witness observation could not be evaluated (e.g. camera hung before reaching Live View).
- **`trace_log_present`**:
  * `yes`: A `TRACE.LOG` file was found on the SD card (under `A/CHDK/LOGS/TRACE.LOG` or root).
  * `no`: No `TRACE.LOG` file was created or found on the SD card.
- **`trace_log_path`**: Relative or absolute path where `TRACE.LOG` was copied on the host workstation (e.g. `candidate_trace/TRACE.LOG`), or `none` if absent.
- **`witness_dump_path`**: Relative or absolute path where raw DRAM or witness dump was saved on the host workstation, or `none` if absent.
- **`outcome_id`**: An outcome identifier from the Outcome Table (`Section 4`):
  * `O1`, `O2`, `O3`, `O4`, `O5`, `O6`, `O7`, `O8`, `O9`, `O10`, `O11`, `O12`, `O13`, `O14`, `O15`, or `O16`.
- **`notes`**: Single-line text summarizing qualitative observations, display strings, unexpected audio cues, or `none`. Attribution of Stage 3 (`O1`) to the current attempt must be explicitly noted as INCONCLUSIVE (`firmware/tools/witness_inspector_gm110c.m:18-24`).

### 6.2 Fenced Results Report Template

The owner fills in the block below:

```port18-report
candidate_sha256: <sha256-recorded-locally>
candidate_size: <size-bytes>
trial_date: 2026-10-31
card_prepared: yes
camera_behaviour: normal_stock_boot
witness_observed: yes
trace_log_present: no
trace_log_path: none
witness_dump_path: none
outcome_id: O1
notes: Observed CONT_ATTEMPTED / FRESHNESS_UNVERIFIED in Live View; attribution to current attempt remains INCONCLUSIVE per firmware/tools/witness_inspector_gm110c.m:18-24.
```
