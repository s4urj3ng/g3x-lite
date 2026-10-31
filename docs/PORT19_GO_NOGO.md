# PORT-19: Owner First-Boot Trial Readiness Verdict

- **Milestone**: PORT-19 (`port-19-trial-blockers`, Task T4)
- **Target Device**: Canon PowerShot G3 X, firmware `GM1.10C`, platform ID `0x32A8` (`12968` decimal), DIGIC 6 / DryOS r57 (`README.md:3`, `docs/FIRMWARE_ACQUISITION_PLAN.md:18-21`)
- **Trial Plan Reference**: `docs/PORT18_OWNER_TRIAL_PLAN.md:1-406`
- **Date**: 2026-10-31
- **Verdict**: **GO**

---

## 1. Executive Summary

Technical readiness for the owner-executed first-boot hardware trial is confirmed, subject to human owner completion of owner-only items P1 and P2 prior to powering on the camera.

All three technical trial blockers identified in `docs/PORT18_OWNER_TRIAL_PLAN.md` (P3 `BOOTDISK` VBR offset, P4 `StartDiskboot` file encoding, and P6 inspector `boot_witness` address alignment) are **`VERIFIED`-resolved** with primary GM1.10C ROM disassembly and host ELF/binary verification:
- **P3 (`VERIFIED`-resolved)**: `"BOOTDISK"` (8 ASCII bytes) is checked at VBR offset **`0x1E0`** (`480` decimal) on **FAT32** and **`0x40`** (`64` decimal) on **FAT12 / FAT16**; `"SCRIPT"` (6 ASCII bytes) is checked at VBR offset **`0x1F0`** (`496` decimal) on **FAT12, FAT16, and FAT32**; **exFAT is `UNSUPPORTED`** (`docs/PORT19_BOOTDISK_VBR.md:13-34, 61-74, 112-259`).
- **P4 (`VERIFIED`-resolved)**: GM1.10C production `StartDiskboot` (`0xFC05BBEA` → `0xFC05BC3C` → `0xFC54DE38` → `0xFC42189C`) requires an **ENCODED** `A/DISKBOOT.BIN` (`dancingbits row 13, byte 0 = 0x00`), which matches the output of `tools/build_candidate_port2a.py` (`118,001` bytes encoded from `118,000` bytes raw `candidate_loader.bin`) (`docs/PORT19_DISKBOOT_ENCODING.md:13-32, 75-323, 348-369`).
- **P6 (`VERIFIED`-resolved)**: The candidate `boot_witness` symbol is pinned at **`0x0035F7A0`** and `_end` at **`0x00366CB0`**, and the candidate build artifacts (`candidate_port2a/witness_inspector_metadata.json`, `candidate_port2a/witness_inspector_payload.bin`, `candidate_port2a/witness_inspector_gm110c.m`), inspector builder/validator (`tools/build_witness_inspector.py:30-42`, `tools/validate_witness_inspector.py:54, 73-79`), and preflight tool (`tools/port18_trial_preflight.py:50, 61, 488-567`) all target and verify `0x0035F7A0` (`docs/PORT19_WITNESS_ADDRESS.md:15-36, 317-426`).
- **P5 (`VERIFIED`)**: Rebuilding and validating the candidate with tracing OFF (`candidate_build`, `candidate_validate`, witness inspector validation, and `tools/port18_trial_preflight.py` with inspector inputs) passed with exit code `0`.

> **Safety Gate Reminder**: Phase 0 remains strictly read-only for autonomous agents (`AGENTS.md:18-22`, `docs/SAFETY.md:3-8`). This technical readiness verdict authorizes the human owner's trial procedure once the owner records explicit phase-transition approval (P1) and confirms `GM1.10C` on the physical camera (P2). No agent connects to hardware, writes SD cards, or executes firmware.

---

## 2. Rebuilt Candidate Measurements (Tracing OFF — Text Record Only)

The candidate was rebuilt from clean bootstrapped sources (`python3 -B tools/bootstrap_chdk_platform.py` followed by `env -u G3X_TRACE python3 -B tools/build_candidate_port2a.py`) and verified with `tools/validate_candidate_port2a.py`, `tools/validate_witness_inspector.py`, and `tools/port18_trial_preflight.py`.

| Artifact / Symbol | Measured Value (Tracing OFF) | Verification Status & Citation |
|---|---|---|
| `candidate_port2a/DISKBOOT.BIN` SHA-256 | `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` | **`VERIFIED`** — matches PORT-16 reference build bit-for-bit (`docs/PORT16_CANDIDATE_BUILD.md:128, 362`; `chdk-port/platform/g3x/sub/110c/g3x_trace.h:12-14`; `tools/port18_trial_preflight.py:449-453`). |
| `candidate_port2a/DISKBOOT.BIN` Size | `118001` bytes (`118,001` B; `0x1CCF1`) | **`VERIFIED`** — 1 leading `0x00` signature byte + `118,000` DancingBits Row 13 scrambled bytes (`docs/PORT19_DISKBOOT_ENCODING.md:25-26, 367`; `docs/PORT16_CANDIDATE_BUILD.md:128, 362`; `tools/build_candidate_port2a.py:569-583`). |
| `boot_witness` Address | `0x0035F7A0` | **`VERIFIED`** — Section `.data`, Type `D`, size `32` bytes (`0x20`), 16-byte aligned (`docs/PORT19_WITNESS_ADDRESS.md:17-20, 325-346`; `docs/PORT16_WITNESS_ADDRESS.md:15, 218`; `tools/build_candidate_port2a.py:54`; `tools/validate_candidate_port2a.py:48`; `tools/port18_trial_preflight.py:50`). |
| `_end` Address (`new_sa` Heap Base) | `0x00366CB0` | **`VERIFIED`** — end of candidate BSS (`0x00365204..0x00366CB0`, `6,828` bytes / `6828` B) (`tools/validate_candidate_port2a.py:52, 54, 472-473`; `docs/PORT16_CANDIDATE_BUILD.md:248-251, 285`; `docs/PORT19_WITNESS_ADDRESS.md:332`; `docs/PORT16_WITNESS_ADDRESS.md:217-218`; `tools/port18_trial_preflight.py:61`). |
| `_start` Address (Core Entry Base) | `0x003489B4` (`0x003489B5` Thumb) | **`VERIFIED`** — start of candidate `.text` in DryOS RAM (`docs/PORT19_WITNESS_ADDRESS.md:330`; `tools/build_candidate_port2a.py:424, 940-941`; `tools/validate_candidate_port2a.py:50`). |
| `candidate_port2a/witness_inspector_payload.bin` Size & Target | `444` bytes; MOVW/MOVT target `0x0035F7A0` | **`VERIFIED`** — `movw r7, #0xf7a0` (`4f f2 a0 77` at offset `0x0A`) and `movt r7, #0x0035` (`c0 f2 35 07` at offset `0x0E`) (`docs/PORT19_WITNESS_ADDRESS.md:20, 355-366`; `tools/port18_trial_preflight.py:523-567`). |
| `candidate_port2a/witness_inspector_metadata.json` Target | `"witness_address": "0x0035F7A0"` | **`VERIFIED`** — generated by `tools/build_candidate_port2a.py:802-805` and verified by `tools/validate_witness_inspector.py:228-239, 475-513` and `tools/port18_trial_preflight.py:488-520` (`docs/PORT19_WITNESS_ADDRESS.md:19, 348-354`). |
| Compile-Time Trace Instrumentation (`G3X_TRACE`) | OFF (`0` trace symbols in `nm`; `g3x_trace_enabled` absent) | **`VERIFIED`** — `tools/port18_trial_preflight.py:83-92, 462-481` confirmed zero `TRACE_FORBIDDEN_SYMBOLS` in `candidate_port2a/candidate_symbols.txt` and `status == "OFFLINE_CANDIDATE_BUILT"` in `candidate_port2a/candidate_manifest.json`. |

---

## 3. Precondition Justifications (P1–P6)

| ID | Precondition | Label & Resolution Status | Justification & Exact Citations |
|---|---|---|---|
| **P1** | Owner phase-transition approval recorded | **OWNER ITEM (`UNKNOWN` until recorded by human owner)** | Phase 0 is read-only for agents regarding firmware and camera hardware `[VERIFIED: AGENTS.md:18-19; docs/SAFETY.md:3-4]`, and any phase transition requires explicit human approval `[VERIFIED: AGENTS.md:22; docs/SAFETY.md:7]`. Whether the human owner has recorded approval for the physical trial is `[UNKNOWN]` in repository state until the owner records it prior to Step 3 of Section 4 below (`docs/PORT18_OWNER_TRIAL_PLAN.md:21`). |
| **P2** | Physical camera internal firmware revision is `GM1.10C` | **OWNER ITEM (`VERIFIED` in prior owner log E037; owner re-confirms on physical camera before trial)** | Recorded from the owner's camera diagnostic screen as `GM1.10C` (`E037`) `[VERIFIED: docs/FIRMWARE_ACQUISITION_PLAN.md:14, 19; docs/RESEARCH_LOG.md:50]`. Because public version `1.1.0.0` covers both `GM1.10C` and `GM1.10E` `[VERIFIED: docs/FIRMWARE_ACQUISITION_PLAN.md:20]`, the public menu version alone is insufficient `[INFERRED: docs/FIRMWARE_ACQUISITION_PLAN.md:20, 25]`. In addition, the Canon Basic witness inspector script checks `"GM1.10C"` at `0xFC54E08D` before executing the native payload and halts with `PORT-1G: ERR_COMPAT` on mismatch `[VERIFIED: firmware/tools/witness_inspector_gm110c.m:42, 176-180; docs/PORT18_OWNER_TRIAL_PLAN.md:22]`. |
| **P3** | `BOOTDISK` and `SCRIPT` VBR marker offsets per filesystem | **RESOLVED (`VERIFIED`)** | Disassembly of the GM1.10C `Mounter.c` VBR inspection function at `0xFC37A4B6-0xFC37A680`, string comparison helper `0xFC37B2AE-0xFC37B2C2`, and `make_bootable` writer `0xFC37B318-0xFC37B38A` proves that `"BOOTDISK"` (8 ASCII bytes at `0xFC37B3A8`) is checked at VBR offset **`0x1E0`** (`480` dec, `movw r1, #480` at `0xFC37A606`; `movw r0, #480` at `0xFC37B372`) on **FAT32** (`Filesystem type = 3` at `0xFC37A5FA`) and at VBR offset **`0x40`** (`64` dec, `movs r1, #64` at `0xFC37A650`; `movs r0, #64` at `0xFC37B356`) on **FAT16** (`type 2` at `0xFC37A63A`) and **FAT12** (`type 1` at `0xFC37A63E`) `[VERIFIED: docs/PORT19_BOOTDISK_VBR.md:13-25, 61-72, 164-206, 232-248]`. `"SCRIPT"` (6 ASCII bytes at `0xFC37A7F0`) is checked at VBR offset **`0x1F0`** (`496` dec, `add.w r0, r4, #496` at `0xFC37A66C`) across **FAT12, FAT16, and FAT32** `[VERIFIED: docs/PORT19_BOOTDISK_VBR.md:27-34, 69-72, 208-222]`. **exFAT (`Filesystem type = 4` at `0xFC37A556`) is `UNSUPPORTED` (`VERIFIED`)**: `0xFC37A55C` (`b.n 0xfc37a67e`) branches past both VBR checks to function exit, leaving `is_bootdisk = 0` and `is_scriptdisk = 0` `[VERIFIED: docs/PORT19_BOOTDISK_VBR.md:24, 33, 73-74, 138-155]`. `EOS_DEVELOP` is not checked by the inspected Mounter VBR routine (`0xFC37A4B6-0xFC37A680`, helper `0xFC37B2AE-0xFC37B2C2`) `[VERIFIED: docs/PORT19_BOOTDISK_VBR.md:36-44]`; whether checked elsewhere in GM1.10C is `[UNKNOWN: docs/PORT19_BOOTDISK_VBR.md:41, 43-44]`. Updated in `docs/PORT18_OWNER_TRIAL_PLAN.md:23, 181-196`. |
| **P4** | `StartDiskboot` accepts the candidate's file encoding | **RESOLVED (`VERIFIED`)** | Disassembly of the complete GM1.10C production SD boot call chain (`task_Startup` `0xFC05B8FC` at `0xFC05B90E` → `StartDiskboot` `0xFC05BBEA` → `sub_fc05bc3c` `0xFC05BC3C` → `sub_fc54de38` `0xFC54DE38` → `sub_fc42189c` `0xFC42189C` → `sub_fc469180` `0xFC469180` / `sub_fc469188` `0xFC469188` → `sub_fc0d9c9c` `0xFC0D9C9C` → `sub_fc0007c0` `0xFC0007C0`) proves that production `StartDiskboot` requires an **ENCODED** `A/DISKBOOT.BIN` (`dancingbits row 13, byte 0 = 0x00`) `[VERIFIED: docs/PORT19_DISKBOOT_ENCODING.md:13-22, 75-323; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:30]`. Specifically, `sub_fc54de38` (`0xFC54DE38`) checks `ldrb r2, [r0, #0]` (`0xFC54DE3A`) and rejects any file with `byte 0 != 0x00` (`cbnz r2, 0xfc54de68` at `0xFC54DE3C`, returning `1` → `"not executable\n"` at `0xFC05BC66-0xFC05BC68`), shifts the buffer left by 1 byte (`0xFC54DE4E-0xFC54DE5E`, setting `r1 = file_size - 1`), and calls `sub_fc42189c` (`0xFC42189C`) to decode `file_size - 1` bytes in-place using DancingBits Row 13 (`[6, 5, 3, 7, 0, 2, 4, 1]` at `0xFC7C0F8C`) before `sub_fc0007c0` copies the decoded payload to `0x40008000` and branches via `bx ip` (`ip = r7 = 0x8001` Thumb) `[VERIFIED: docs/PORT19_DISKBOOT_ENCODING.md:153-323]`. Raw `DISKBOOT.BIN` is incompatible (the raw loader at `0xFC0005A0` is the factory `RomStarter` rescue path at `0xFC0004AE`) `[VERIFIED: docs/PORT19_DISKBOOT_ENCODING.md:19-22, 327-344]`. `tools/build_candidate_port2a.py:569-583` produces the exact 118,001-byte encoded `candidate_port2a/DISKBOOT.BIN` required by `StartDiskboot`, and `tools/validate_candidate_port2a.py:81-93, 457-463` verifies round-trip decoding to `candidate_loader.bin` (`118,000` B) `[VERIFIED: docs/PORT19_DISKBOOT_ENCODING.md:24-32, 348-369]`. Updated in `docs/PORT18_OWNER_TRIAL_PLAN.md:24, 198-205`. |
| **P5** | Host build, validation, and preflight exit `0` | **RESOLVED (`VERIFIED` on clean worktree rebuild; owner re-runs on host before card prep)** | Executed with tracing OFF (`env -u G3X_TRACE`): `tools/bootstrap_chdk_platform.py` (exit `0`), `tools/build_candidate_port2a.py` (exit `0`, `DISKBOOT.BIN` `118,001` B, SHA-256 `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136`, `boot_witness = 0x0035F7A0`, `_end = 0x00366CB0`), `tools/validate_candidate_port2a.py` (exit `0`, 7/7 suites PASS), `tools/validate_witness_inspector.py` with candidate artifacts and `--expected-addr 0x0035F7A0` (exit `0`, PASS), and `tools/port18_trial_preflight.py` with `--inspector-metadata candidate_port2a/witness_inspector_metadata.json --inspector-bin candidate_port2a/witness_inspector_payload.bin` (exit `0`, verdict `PASS`) `[VERIFIED: Section 2 above; docs/PORT18_OWNER_TRIAL_PLAN.md:25, 28-102]`. Note: per `docs/PORT17_TRACE_EVIDENCE.md:232-235` and `docs/PORT18_OWNER_TRIAL_PLAN.md:115-119`, OFF-linker-stanza absence in `candidate_main.map` is verified on the host during Step 1 below (`INFERRED` in plan prose until the owner runs Step 1 on their host). |
| **P6** | Inspector witness address alignment (`0x0035F7A0`) | **RESOLVED (`VERIFIED`)** | Authoritative symbol table (`arm-none-eabi-nm` and `arm-none-eabi-readelf -s`) on `candidate_port2a/candidate_main.elf` proves `boot_witness = 0x0035F7A0` (Section `.data`, Type `D`, 32 B, 16-byte aligned) and `_end = 0x00366CB0` `[VERIFIED: docs/PORT19_WITNESS_ADDRESS.md:17-20, 317-346; docs/PORT16_WITNESS_ADDRESS.md:15, 218]`. The candidate build outputs (`candidate_port2a/witness_inspector_metadata.json`, `candidate_port2a/witness_inspector_payload.bin` with `movw r7, #0xf7a0` / `movt r7, #0x0035` at `0x0A`/`0x0E`, and `candidate_port2a/witness_inspector_gm110c.m`), the inspector builder/validator (`tools/build_witness_inspector.py:30, 37, 39, 42`, `tools/validate_witness_inspector.py:54, 73, 75, 78`), and the preflight tool (`tools/port18_trial_preflight.py:50, 61, 488-567`) all pin and verify `0x0035F7A0`, default to `candidate_port2a/`, and reject the historical pre-correction `firmware/tools/` baseline fail-closed `[VERIFIED: docs/PORT19_WITNESS_ADDRESS.md:21-36, 60, 348-426]`. Updated in `docs/PORT18_OWNER_TRIAL_PLAN.md:11, 26, 69-100`. |

---

## 4. Owner Step-by-Step Execution Checklist

The human owner performs these steps by hand on the host workstation and physical camera only after recording explicit phase-transition approval (P1) and confirming `GM1.10C` on the camera (P2) (`docs/PORT18_OWNER_TRIAL_PLAN.md:21-22, 165-173`). No agent performs Steps 3–5.

### Step 1 — Build and Validate on the Host (`docs/PORT18_OWNER_TRIAL_PLAN.md:28-143`)

Run from the repository root on the host workstation:

```bash
# 1. Verify pinned toolchain (5.4.1 20160919)
toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-gcc --version

# 2. Bootstrap deterministic platform source tree
python3 -B tools/bootstrap_chdk_platform.py

# 3. Clean any prior build directories
rm -rf candidate_port2a candidate_trace

# 4. Build candidate with tracing OFF
env -u G3X_TRACE python3 -B tools/build_candidate_port2a.py

# 5. Generate link map for layout inspection (docs/PORT17_TRACE_EVIDENCE.md:106-125)
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

# 6. Validate candidate (7 suites; must exit 0)
python3 -B tools/validate_candidate_port2a.py

# 7. Validate witness inspector artifacts against candidate ELF (must exit 0)
python3 -B tools/validate_witness_inspector.py \
  --elf candidate_port2a/candidate_main.elf \
  --payload-bin candidate_port2a/witness_inspector_payload.bin \
  --payload-elf candidate_port2a/witness_inspector_payload.o \
  --loader-script candidate_port2a/witness_inspector_gm110c.m \
  --metadata candidate_port2a/witness_inspector_metadata.json \
  --expected-addr 0x0035F7A0

# 8. Confirm tracing OFF in manifest, linker script, and link map (every command exits 0 when OFF)
grep -n '"status"' candidate_port2a/candidate_manifest.json          # expect OFFLINE_CANDIDATE_BUILT
test -r candidate_port2a/candidate_manifest.json && ! grep -q -- 'g3x_trace_enabled' candidate_port2a/candidate_manifest.json && echo "OK: g3x_trace_enabled absent in candidate_port2a/candidate_manifest.json" || { echo "FAIL: g3x_trace_enabled present or read error in candidate_port2a/candidate_manifest.json"; false; }
test -r chdk-port/tools/link-boot.ld && ! grep -q -E -- '(g3x_trace|KEEP)' chdk-port/tools/link-boot.ld && echo "OK: (g3x_trace|KEEP) absent in chdk-port/tools/link-boot.ld" || { echo "FAIL: (g3x_trace|KEEP) present or read error in chdk-port/tools/link-boot.ld"; false; }
test -r candidate_port2a/candidate_main.map && ! grep -q -i -- 'g3x_trace' candidate_port2a/candidate_main.map && echo "OK: g3x_trace absent in candidate_port2a/candidate_main.map" || { echo "FAIL: g3x_trace present or read error in candidate_port2a/candidate_main.map"; false; }
grep -E '(boot_witness|_end$)' candidate_port2a/candidate_main.map    # expect 0x0035f7a0 and 0x00366cb0
```

### Step 2 — Run Preflight with Inspector Inputs (`docs/PORT18_OWNER_TRIAL_PLAN.md:80-91, 146-165`)

```bash
# 1. Extract symbol table from candidate ELF
toolchains/gcc-arm-none-eabi-5_4-2016q3/bin/arm-none-eabi-nm \
  candidate_port2a/candidate_main.elf > candidate_port2a/candidate_symbols.txt

# 2. Run preflight verification with inspector metadata and payload binary
mkdir -p private/port18
python3 -B tools/port18_trial_preflight.py \
  candidate_port2a/DISKBOOT.BIN \
  candidate_port2a/candidate_symbols.txt \
  --inspector-metadata candidate_port2a/witness_inspector_metadata.json \
  --inspector-bin candidate_port2a/witness_inspector_payload.bin \
  --out private/port18/preflight_report.json

# 3. Record local measurements and confirm match with Section 2 above:
#    SHA-256 = 9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136
#    Size    = 118001 bytes
#    boot_witness = 0x0035F7A0, _end = 0x00366CB0
{ sha256sum candidate_port2a/DISKBOOT.BIN; stat -c 'size %s' candidate_port2a/DISKBOOT.BIN; } \
  > private/port18/candidate_measurements.txt
```

Every command in Step 1 and Step 2 (including the trace-absence checks in Step 1.8, which exit `0` and print `OK:` when the trace markers are absent) exits `0` on a valid tracing-OFF candidate; if any command in Step 1 or Step 2 exits non-zero or produces a mismatched hash/size/address, **stop immediately** and do not prepare an SD card (`docs/PORT18_OWNER_TRIAL_PLAN.md:103, 144, 165`).

### Step 3 — Prepare the SD Card (`docs/PORT18_OWNER_TRIAL_PLAN.md:177-218`)

1. **Dedicated card & filesystem (`docs/PORT18_OWNER_TRIAL_PLAN.md:181-185`)**: Use a dedicated spare SD card (recommended ≤ 32 GB SDHC with MBR and a single primary **FAT32** or **FAT16** partition). **Do NOT use exFAT** (`exFAT` is `UNSUPPORTED` in `Mounter.c` at `0xFC37A55C`, `docs/PORT19_BOOTDISK_VBR.md:24, 33, 73-74, 138-155`).
2. **Write VBR signatures (`docs/PORT18_OWNER_TRIAL_PLAN.md:187-196`, `docs/PORT19_BOOTDISK_VBR.md:18-34`)**: In the FAT partition's Volume Boot Record (sector 0 of the partition, **not** the MBR):
   - Write `"BOOTDISK"` (8 ASCII bytes: `42 4F 4F 54 44 49 53 4B`) at VBR offset **`0x1E0`** (`480` dec) on **FAT32**, or at VBR offset **`0x40`** (`64` dec) on **FAT12 / FAT16**.
   - Write `"SCRIPT"` (6 ASCII bytes: `53 43 52 49 50 54`) at VBR offset **`0x1F0`** (`496` dec) on **FAT12, FAT16, or FAT32**.
3. **Copy root files (`docs/PORT18_OWNER_TRIAL_PLAN.md:198-212`)**:
   - `candidate_port2a/DISKBOOT.BIN` → `<card_root>/DISKBOOT.BIN` (**ENCODED**, `118,001` bytes, DancingBits Row 13, byte 0 = `0x00`, SHA-256 `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136`; do **not** copy raw `candidate_loader.bin`).
   - `candidate_port2a/witness_inspector_gm110c.m` → `<card_root>/extend.m`.
   - `candidate_port2a/witness_inspector_payload.bin` → `<card_root>/WITNESS.BIN` (`444` bytes, targeting `0x0035F7A0`; do **not** copy from `firmware/tools/`).
   - Create `<card_root>/script.req` containing `for DC_scriptdisk` (`17` ASCII bytes, no newline: `printf 'for DC_scriptdisk' > <card_root>/script.req`).
   - Ensure no `TRACE.LOG` exists on the card (`rm -f <card_root>/TRACE.LOG <card_root>/CHDK/LOGS/TRACE.LOG`).
   - Verify each copied file on the card against its host source with `cmp`.
4. **Unmount and lock (`docs/PORT18_OWNER_TRIAL_PLAN.md:214-218`)**: Run `sync`, unmount the card cleanly, and slide the physical SD card write-protect tab to **LOCKED** (`StartDiskboot` checks the switch at `0xFC05BC04`, `docs/PORT19_DISKBOOT_ENCODING.md:89-93`).

### Step 4 — Run the Physical Trial (`docs/PORT18_OWNER_TRIAL_PLAN.md:220-252`)

Perform in a single powered session (because `boot_witness` at `0x0035F7A0` is in volatile DRAM):

1. **Insert (`Step 1`)**: With the camera OFF, insert a fully charged battery and the **LOCKED** SD card, and close the compartment door.
2. **Power on in Playback mode (`Step 2`)**: Press the **Playback** button (lens stays retracted). Start a stopwatch and observe LCD, LEDs, and sounds.
3. **Observe stock Playback UI (`Step 3`)**: Verify normal Canon Playback screen ("No images" or photo view). If the camera hangs, goes black, or reboot-loops, proceed immediately to **Step 5 (Recovery)** below.
4. **Activate Canon Basic inspector (`Step 4`)**: Press **`FUNC./SET`** once in Playback mode. Canon Basic runs `extend.m`, loads `A/WITNESS.BIN` (`444` B), invokes the payload to inspect `boot_witness` at `0x0035F7A0`, and registers `h_title` and `h_status` OSD message descriptors.
5. **Switch to Shooting mode / Live View (`Step 5`)**: Without powering off, half-press the shutter button (or press the Playback/Shooting button) to enter Shooting mode (Live View) so the retained 112-byte OSD descriptors render unoccluded.
6. **Observe and photograph LCD (`Step 6`)**: Photograph the two-line OSD readout (`h_title` at x=60, y=140; `h_status` at x=60, y=180, e.g., `CONT_ATTEMPTED` / `FRESHNESS_UNVERIFIED` for Stage 3 `O1`).
7. **Power off and remove card (`Step 7`)**: Power off normally (or pull battery if unresponsive), remove the SD card, and return it to the host.

### Step 5 — Recovery Procedure (`docs/PORT18_OWNER_TRIAL_PLAN.md:318-353`)

Recovery expectations are qualified as in the trial plan (`docs/PORT18_OWNER_TRIAL_PLAN.md:320-327`). No physical recovery step has been tested on this camera (**untested**). An unlocked card, no card, or a card without the `BOOTDISK` marker only keeps `DISKBOOT.BIN` from loading at the **next** power-on (R-a, R-b; that this leads to a normal stock start is `[INFERRED]`). None of these can stop a payload that is already running or hung. The candidate runs only from RAM, and that a power cycle removes it is `[INFERRED]` (R-d). The likelihood of the listed persistence risks (flash/EEPROM corruption by downstream code, mechanical damage, watchdog loops) is `[UNKNOWN]` (`docs/PORT18_OWNER_TRIAL_PLAN.md:327`). A return to stock boot is therefore not guaranteed. Follow the plan's ordering: remove the battery first to power-cycle, then remove the card, and before the card goes near the camera again unlock it, rename `DISKBOOT.BIN` or reformat it on the host so the `BOOTDISK` marker is gone (`docs/PORT18_OWNER_TRIAL_PLAN.md:331-337`).

- **Hang (`O8`, `O9` — `docs/PORT18_OWNER_TRIAL_PLAN.md:329-337`)**:
  1. Do not press buttons repeatedly `[INFERRED]`.
  2. Open the battery door and remove the battery `[INFERRED]`.
  3. Remove the card `[INFERRED: R-a]`.
  4. Leave the camera without power for at least 30 s `[INFERRED]`.
  5. Put the battery back with **no card**. Power on in Playback `[INFERRED: R-a]`.
  6. Confirm stock behaviour: normal Playback screen, then Shooting mode with live view and responsive menus `[INFERRED]`. If it is not normal, go to the abort rule (Abnormal state, step 5).
  7. On the host, make the card safe before it goes near the camera again: unlock it (R-a), or rename `DISKBOOT.BIN`, or reformat `[INFERRED: R-a, R-b]`.
- **No boot / no power-on (`O10`, `O15` — `docs/PORT18_OWNER_TRIAL_PLAN.md:339-345`)**:
  1. Remove the battery and the card `[INFERRED]`.
  2. Check the battery's charge in the charger and recharge it `[INFERRED]`.
  3. Check that the battery/card door latches `[INFERRED]`.
  4. Insert the charged battery with **no card**, close the door and press Playback `[INFERRED: R-a]`.
  5. If still dead: leave it without a battery for a longer period, then retry once with no card `[INFERRED]`. If it is still dead, stop and report. Further recovery is `[UNKNOWN]`.
- **Abnormal state (`O11`, `O12`, `O16` — `docs/PORT18_OWNER_TRIAL_PLAN.md:347-353`)**:
  1. Remove the battery at once. Do not let a restart loop continue `[INFERRED]`.
  2. Remove the card and keep it unmodified for host inspection `[INFERRED]`.
  3. On the host, list the card contents. Parse any `TRACE.LOG` with `python3 tools/port17_trace_parser.py <path> -H`. Its origin is `[UNKNOWN]`.
  4. Insert the battery with **no card** and power on in Playback `[INFERRED: R-a]`.
  5. **Abort rule**: if stock behaviour does not return (lens error, black screen, error codes, restart loop), **stop, do not retry**, and report with Step 6 `[INFERRED]`. Recovery beyond this point is `[UNKNOWN]`.

### Step 6 — Report Results with `tools/port18_trial_report.py` (`docs/PORT18_OWNER_TRIAL_PLAN.md:254-316, 357-406`)

1. Copy the `port18-report` block template from `docs/PORT18_OWNER_TRIAL_PLAN.md:394-406` to `private/port18/trial_report.md` and fill in the observed values (`candidate_sha256`, `candidate_size`, `trial_date`, `card_prepared`, `camera_behaviour`, `witness_observed`, `trace_log_present`, `trace_log_path`, `witness_dump_path`, `outcome_id` from `O1`–`O16`, and `notes`).
2. **Manual candidate measurement comparison**: Before running `tools/port18_trial_report.py`, manually compare the `DISKBOOT.BIN` SHA-256 (`candidate_sha256`) and byte size (`candidate_size`) recorded in `private/port18/trial_report.md` against the preflight output (`private/port18/preflight_report.json` and `private/port18/candidate_measurements.txt` from Step 2) and against the verified values in Section 2 of this document (`9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136`, `118001` bytes). (`tools/port18_trial_report.py` validates key/value schema and format only; it does not accept a preflight file or compare candidate measurements against preflight output.)
3. Run the report-ingest and classification tool (`tools/port18_trial_report.py:1354-1469`) against the filled report:

```bash
python3 -B tools/port18_trial_report.py \
  private/port18/trial_report.md \
  --strict \
  --out private/port18/ingested_trial_report.json
```

(If a `TRACE.LOG` or witness dump was collected, also pass `--trace-log` and/or `--witness-dump`, optionally with `--expected-nonce <nonce>`.)
4. Verify that `tools/port18_trial_report.py` exits `0`. When `--out` is passed, the tool prints:
   - `Report ingested: private/port18/trial_report.md`
   - `Outcome classification: <outcome_id or classification_status>` (e.g., `O1`–`O16` or `insufficient_evidence`)
   - `Summary written to: private/port18/ingested_trial_report.json`
   (and if the owner's `outcome_id` disagrees with the implied outcome derived from the Section 4.2 decision matrix, it prints `WARNING: Outcome mismatch flagged: ...` on `stderr` and exits `1` under `--strict`; if `--out` is omitted, it prints the JSON summary object containing `"status": "ok"`, `"report_file"`, `"parsed_fields"`, `"report_fields"`, `"tool_results"`, `"outcome_classification"`, and `"ingest_timestamp"` to `stdout`). Keep `private/port18/` untracked (`git status --short` must remain clean).
