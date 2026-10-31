# PORT-22 Remediation Plan: Remediation Design for Hypotheses H1–H4

- **Target Architecture**: DIGIC 6 (Cortex-R4 / ARMv7-R) `[VERIFIED: docs/PORT21_WITNESS_AUDIT.md:131; docs/PORT21_DISKBOOT_TIMING.md:3]`
- **Target Firmware**: PowerShot G3 X GM1.10C (Platform ID `0x32A8` = 12968 dec) `[VERIFIED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:6; docs/PORT21_OWNER_SESSION_PLAN.md:3]`
- **Authority and Scope**: Phase 0 research design; strictly read-only regarding firmware and hardware; no ROM dump reads or binary execution `[VERIFIED: docs/PORT16_CANDIDATE_BUILD.md:6, 27; docs/PORT21_DISKBOOT_TIMING.md:4]`

---

## 1. Overview and Epistemic Framework

- Grounding in PORT-21 T4 Owner Session Plan: The candidate hypotheses H1, H2, H3, and H4 evaluated herein are taken directly from the offline analysis of Observation O6 (`docs/PORT21_OWNER_SESSION_PLAN.md:34-43`) `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:34-43]`.
- Epistemic labelling policy: Every claim, candidate change, supporting fact, and confirming reading is explicitly labeled `[VERIFIED]`, `[INFERRED]`, or `[UNKNOWN]` `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:165-167; docs/PORT16_FIRSTBOOT_U_TRIAGE.md:28-30]`.
- Citation requirement: All evidential assertions cite existing repository documents or evidence manifests using exact `path:line` or `path:start-end` syntax `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:166-167, 282-289]`.
- Strict prohibition against guessing: If an address, offset, CPU mode, or ROM range is not already evidenced in `docs/PORT16_*` through `docs/PORT21_*` or `docs/agentbridge/PORT*_EVIDENCE_MANIFEST.json`, it is designated `[UNKNOWN]` to be resolved in a later milestone `[VERIFIED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:524-525; docs/PORT21_OWNER_SESSION_PLAN.md:165-167]`.

---

## 2. Hypothesis H1: Candidate Rejected by Gate in `StartDiskboot`

### 2.1 Hypothesis Definition and Grounding
- **Definition**: `StartDiskboot` never reached loader (ROM rejected binary or skipped loading) `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:38]`.
- **Mechanism**: If `StartDiskboot` rejected the candidate binary at Gate 1 (`byte 0 != 0x00`) or Gate 2 (`gaonisoy` match) in `sub_fc54de38` (`0xFC54DE38`), it printed `"not executable\n"` at `0xFC05BC68`, freed the temporary memory buffer at `0xFC05BC70`, and returned cleanly to `task_Startup` at `0xFC05BC38` without executing the loader `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:38; docs/PORT21_DISKBOOT_TIMING.md:32-37, 126-128; docs/agentbridge/PORT19_EVIDENCE_MANIFEST.json:14-17]`.
- **Timing Impact**: The reject path performs SD card initialization, FAT directory lookup, and reads 118,001 bytes into DRAM before reaching `sub_fc54de38`, accounting for ~100–250 ms overhead `[INFERRED: docs/PORT21_DISKBOOT_TIMING.md:24-30, 48]`. Thus, a slower start-up only when the card is locked does not rule out H1 `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:38; docs/PORT21_DISKBOOT_TIMING.md:30]`.
- **Offline Evaluation**: FITS / UNTESTED on physical hardware `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:38]`. Whether the file present on the owner's SD card during trial O6 matched the host candidate build bit-for-bit is strictly `[UNKNOWN: docs/PORT21_DISKBOOT_TIMING.md:244; docs/PORT21_OWNER_SESSION_PLAN.md:38]`.

### 2.2 Next Candidate Change
- **Target File**: `tools/build_candidate_port2a.py` `[VERIFIED: docs/PORT16_CANDIDATE_BUILD.md:18, 107; docs/PORT21_DISKBOOT_TIMING.md:51]`
- **Target Function**: `encode_candidate_diskboot` and `encode_dancingbits_row13` in `tools/build_candidate_port2a.py` `[INFERRED: docs/PORT16_CANDIDATE_BUILD.md:107; docs/PORT19_DISKBOOT_ENCODING.md:191, 339-340]`

#### Candidate Change Details
- Remediate the DISKBOOT encoding pipeline to strictly enforce Gate 1 header requirements by prepending `b"\x00"` at byte offset 0 `[VERIFIED: docs/PORT19_DISKBOOT_ENCODING.md:20-21, 153-154]`.
- Enforce Gate 2 validation ensuring offsets 16 and 32 in the encoded stream do not match `"gaonisoy"` `[VERIFIED: docs/PORT21_DISKBOOT_TIMING.md:128; docs/agentbridge/PORT19_EVIDENCE_MANIFEST.json:14-17]`.
- Validate DancingBits Row 13 permutation table integrity across all 8-byte blocks `[VERIFIED: docs/PORT19_DISKBOOT_ENCODING.md:191, 339-340; docs/PORT21_DISKBOOT_TIMING.md:131-133]`.
- Audit SD card FAT32 cluster alignment and file allocation table directory entry positioning in `tools/build_candidate_port2a.py` to ensure cluster bounds satisfy GM1.10C ROM reader requirements `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:218; docs/PORT21_DISKBOOT_TIMING.md:32-37, 298-302]`.

### 2.3 Supporting Evidence
- ROM function `sub_fc54de38` (`0xFC54DE38`) at `0xFC54DE3C` explicitly checks `byte 0 == 0x00`, immediately returning 1 ("not executable") if non-zero `[VERIFIED: docs/PORT19_DISKBOOT_ENCODING.md:20-21, 153-154; docs/agentbridge/PORT19_EVIDENCE_MANIFEST.json:14-17]`.
- ROM function `sub_fc54de38` at `0xFC54DE4C` checks for `"gaonisoy"`, returning 1 if matched `[VERIFIED: docs/PORT21_DISKBOOT_TIMING.md:128; docs/agentbridge/PORT19_EVIDENCE_MANIFEST.json:14-17]`.
- When `sub_fc54de38` returns 1, `StartDiskboot` branches to `0xFC05BC68`, prints `"not executable\n"`, frees buffer `0xFC05BC70`, and aborts boot without copying to `0x40008000` `[VERIFIED: docs/PORT21_DISKBOOT_TIMING.md:32-37, 141-149; docs/agentbridge/PORT19_EVIDENCE_MANIFEST.json:10-13]`.
- Shift loop in `sub_fc54de38` (`0xFC54DE4E..0xFC54DE5E`) shifts payload left by 1 byte, overwriting byte 0, and decrements length register `r1` by 1 (`subs r1, r1, #1`) before passing to DancingBits decoder `sub_fc42189c` `[VERIFIED: docs/PORT19_DISKBOOT_ENCODING.md:191, 318; docs/agentbridge/PORT19_EVIDENCE_MANIFEST.json:14-21]`.
- Host candidate build `9468257364...` passes Gate 1 and Gate 2 statically `[VERIFIED: docs/PORT21_DISKBOOT_TIMING.md:51, 56, 278]`.

### 2.4 Follow-Up Owner Reading
- **Physical Test Procedure**: Owner inserts locked SD card with candidate `DISKBOOT.BIN`, powers on via Playback button, observes rear LED, and executes Canon Basic `extend.m` `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:97-121]`.

#### Confirming Owner Reading Outcomes
- Refuting H1 (Loader Reached / Gate Passed): Rear green status LED (GPIO 33, MMIO `0xD20B0884`) pulses for ~1–2 s immediately after power-on, proving loader entry was reached; or, if no LED pulse is observed, Canon Basic RAMCMP reports `r_l4 == 1` in uncached DRAM alias `0x40008000` (which is checked only when no LED pulse occurs because `r_l4` survival across reboot is otherwise `[UNKNOWN]`), confirming `StartDiskboot` accepted and copied the binary `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:48, 147, 191-195; docs/PORT20_LED_CANDIDATE.md:31-37; docs/PORT21_DISKBOOT_TIMING.md:301-302]`.
- Confirming H1 (Rejection Persists): No rear LED pulse (0 s delay), fast boot into stock Playback UI, and Canon Basic RAMCMP reports `r_l4 == 0` at `0x40008000` (unwritten DRAM), confirming ROM rejected `DISKBOOT.BIN` at `sub_fc54de38` without copying `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:171, 191-192; docs/PORT21_DISKBOOT_TIMING.md:302]`.

---

## 3. Hypothesis H2: Loader Stopped at `check_compat()`

### 3.1 Hypothesis Definition and Grounding
- **Definition**: Loader ran, but stopped at `check_compat()` `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:39]`.
- **Mechanism**: In `check_compat()`, a platform ID or firmware revision mismatch causes execution to enter `blink()`, which executes an infinite busy loop (`while(1)`) `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:39; docs/PORT21_RAM_LIFETIME.md:283-286; docs/PORT21_DISKBOOT_TIMING.md:280-282]`.
- **Offline Evaluation**: RULED OUT for uninterrupted execution (because camera reached stock Playback UI in O6); UNTESTED if a hardware watchdog timer subsequently rebooted into stock ROM `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:39; docs/PORT21_RAM_LIFETIME.md:286]`.

### 3.2 Next Candidate Change
- **Target File**: `tools/build_candidate_port2a.py` `[VERIFIED: docs/PORT16_CANDIDATE_BUILD.md:18, 107; docs/PORT21_DISKBOOT_TIMING.md:51]`
- **Target Function**: `build_candidate_loader` in `tools/build_candidate_port2a.py` `[INFERRED: docs/PORT16_CANDIDATE_BUILD.md:107; docs/PORT21_RAM_LIFETIME.md:58-61]`

#### Candidate Change Details
- In `build_candidate_loader`, audit and remediate compiler macro definitions and platform configuration flags (such as `-DPLATFORMID=12968`) passed to the loader build `[INFERRED: docs/PORT16_CANDIDATE_BUILD.md:107; docs/PORT21_WITNESS_AUDIT.md:42; docs/PORT21_RAM_LIFETIME.md:58-61]`.
- In `check_pid()` compatibility verification, verify that platform ID pointer dereferences compare against `PLATFORMID` (`0x32A8` = 12968 dec) `[VERIFIED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:6; docs/PORT21_DISKBOOT_TIMING.md:3]`, while the hardware MMIO or ROM address for reading the physical platform ID (previously hypothesized as `0xFDF20270`) is `[UNKNOWN: no allowed source verifies 0xFDF20270; docs/PORT21_RAM_LIFETIME.md:58-63]`.
- In `check_compat()` compatibility verification, verify version comparison against ROM string `"GM1.10C"` at `0xFC54E08D` `[VERIFIED: docs/PORT18_OWNER_TRIAL_PLAN.md:22; docs/PORT19_GO_NOGO.md:47]`.
- In `blink()`, replace silent infinite hang with active GPIO 33 LED toggle (`0xD20B0884`) or bounded retry before fallback `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:223; docs/PORT20_LED_CANDIDATE.md:31-37; docs/PORT21_RAM_LIFETIME.md:283-286]`.
- In candidate loader generation, verify that candidate loader entry sequence invokes compatibility verification after prologue LED initialization `[INFERRED: docs/PORT20_LED_CANDIDATE.md:122-142; docs/PORT21_RAM_LIFETIME.md:58-63]`.

### 3.3 Supporting Evidence
- GM1.10C Platform ID is `0x32A8` (12968 dec) `[VERIFIED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:6; docs/PORT21_DISKBOOT_TIMING.md:3]`, whereas the MMIO/ROM address for reading the physical platform ID (hypothesized as `0xFDF20270`) does not appear in any allowed source and remains `[UNKNOWN: no allowed source verifies 0xFDF20270; docs/PORT21_RAM_LIFETIME.md:58-63]`.
- Firmware version string `"GM1.10C"` is confirmed at `0xFC54E08D` `[VERIFIED: docs/PORT18_OWNER_TRIAL_PLAN.md:22; docs/PORT19_GO_NOGO.md:47]`.
- In compatibility verification, if the platform ID check fails, execution falls through to `blink()` `[INFERRED: docs/PORT21_RAM_LIFETIME.md:283-286; docs/PORT21_DISKBOOT_TIMING.md:248, 282]`.
- In compatibility verification, if version comparison fails, execution similarly invokes `blink()` `[INFERRED: docs/PORT21_RAM_LIFETIME.md:283-286; docs/PORT21_DISKBOOT_TIMING.md:248, 282]`.
- Function `blink()` executes an infinite loop `while(1)` toggling LED or halting `[INFERRED: docs/PORT21_RAM_LIFETIME.md:283-286; docs/PORT21_DISKBOOT_TIMING.md:282]`.
- Whether GM1.10C hardware watchdog resets after hang in `check_compat()` is `[UNKNOWN: docs/PORT21_OWNER_SESSION_PLAN.md:39; docs/PORT21_DISKBOOT_TIMING.md:251, 282]`.

### 3.4 Follow-Up Owner Reading
- **Physical Test Procedure**: Power on with locked card containing candidate `DISKBOOT.BIN` and observe boot outcome `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:97-121]`.

#### Confirming Owner Reading Outcomes
- Refuting H2 (Compatibility Verified): Camera does not hang; rear LED pulses for ~1–2 s and camera proceeds to display stock Playback UI within ~2.5–3.5 s `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:104-107, 195-197]`. Canon Basic `extend.m` executes successfully upon pressing FUNC./SET `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:109-110, 197]`.
- Confirming H2 (Compatibility Failure): Camera hangs permanently with black screen and unhandled LED blinking pattern after initial ~1–2 s pulse, never reaching stock Playback UI `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:172, 195-196; docs/PORT21_DISKBOOT_TIMING.md:280-282]`. Canon Basic cannot run; camera requires battery pull recovery `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:172, 245-260]`.

---

## 4. Hypothesis H3: Loader Wrote Witness, Overwritten by Stock Boot

### 4.1 Hypothesis Definition and Grounding
- **Definition**: Loader wrote witness, but stock boot later overwrote `0x0035F7A0` `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:40]`.
- **Mechanism**: Loader executed and wrote the Stage 1 witness record at `0x0035F7A0`. However, the software reboot trampoline in `boot_prototype.c` failed to complete the dynamic heap shift (`new_sa = 0x00366CB0`), or faulted into a stock ROM warm reset. Stock ROM initialized the heap at default base `0x003489B4` (spanning `0x0035F7A0` at offset `+0x16DEC`), and subsequent stock allocations overwrote the witness record before Canon Basic ran `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:40, 225-228; docs/PORT21_RAM_LIFETIME.md:46-48, 287-293]`.
- **Offline Evaluation**: FITS / UNTESTED on physical hardware `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:40]`. Whether stock boot actively overwrites `0x0035F7A0` before Canon Basic runs is strictly `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:47, 247-249, 269, 290]`.

### 4.2 Next Candidate Change
- **Target File**: `chdk-port/platform/g3x/sub/110c/boot_prototype.c` `[VERIFIED: docs/PORT16_CANDIDATE_BUILD.md:107; docs/PORT21_RAM_LIFETIME.md:58-61]`
- **Target Function**: `sub_fc05b3c8_my` and `boot` in `chdk-port/platform/g3x/sub/110c/boot_prototype.c` `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:118-125, 172-178]`

#### Candidate Change Details
- In `sub_fc05b3c8_my`, enforce strict AAPCS 8-byte stack alignment when allocating the 120-byte (`0x78`) setup structure (`sub sp, #0x78`) `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:127]`.
- In `sub_fc05b3c8_my`, verify shifted heap parameters: ensure `new_sa` (`0x00366CB0`) is stored at `sp[0x08]` and remaining heap size `0x00600014 - new_sa` (`0x00299364`) at `sp[0x0C]` before calling `sub_fc31b408` (`0xFC31B408`) `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:129-130, 238, 294-295]`.
- In `boot()`, ensure CPU mode (Supervisor vs System) and `cpsid if` configuration are explicitly handled `[UNKNOWN: CPU mode and cpsid if are UNKNOWN per docs/PORT21_OWNER_SESSION_PLAN.md:228; docs/PORT21_RAM_LIFETIME.md:109-125]` before executing Copy Loop 3 (`0x00008000..0x0003F4F4`) and BSS zeroing (`0x0003F4F4..0x003489B4`) `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:120-123]`.
- Debug MPU Region 7 configuration (`0xFC0D9CB0`) and cache maintenance call `sub_fc127a62` (`[UNKNOWN: address 0xFC127A62 not in allowed sources; routine sub_fc127a62 cited in docs/PORT16_FIRSTBOOT_U_TRIAGE.md:56; docs/PORT21_OWNER_SESSION_PLAN.md:228; docs/PORT21_DISKBOOT_TIMING.md:46]`) to prevent data abort exceptions during heap construction `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:228; docs/PORT16_FIRSTBOOT_U_TRIAGE.md:56; docs/PORT21_DISKBOOT_TIMING.md:46]`.

### 4.3 Supporting Evidence
- In stock GM1.10C ROM, DryOS heap base is configured at `0x003489B4` and extends to `0x00600014` `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:46-48, 243-244; docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json:14-17]`.
- Witness address `0x0035F7A0` lies within the stock heap range at offset `+0x16DEC` (93,676 B) above `0x003489B4` `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:47, 244]`.
- The candidate heap shift relocates the heap base to `new_sa = 0x00366CB0`, protecting `0x003489B4..0x00366CB0` (including witness at `0x0035F7A0`) from DryOS dynamic allocation `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:238, 294-295]`.
- Authorized ROM slices `PORT21-ROM-HEAP-SETUP` (`0xFC05B3C0..0xFC05B53F`) and `PORT21-ROM-INIT-TASK` (`0xFC05B540..0xFC05B73F`) verify stock heap allocation structure `[VERIFIED: docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json:14-25]`.
- If soft restart faults in `boot()` or `sub_fc05b3c8_my`, ROM reset handler reinitializes heap at `0x003489B4`, destroying witness data `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:40, 225-228; docs/PORT21_RAM_LIFETIME.md:287-293]`.

### 4.4 Follow-Up Owner Reading
- **Physical Test Procedure**: Power on with locked card containing candidate `DISKBOOT.BIN`, reach stock Playback UI, and launch Canon Basic `extend.m` `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:97-121]`.

#### Confirming Owner Reading Outcomes
- Refuting H3 (Heap Shift Protected Memory): Canon Basic RAMCMP reports `r_c4 == 1` at `0x003489B4` (core intact against `REF_C.BIN`), `r_ct == 1` at `0x00349798` (continuation code intact), and `r_wm == 1` at `0x0035F7A0` (witness valid), with Inspector OSD displaying `LOADER_REACHED` (Color 1,4 White/Yellow) or `CONT_ATTEMPTED` (Color 4,4 Yellow/Yellow) `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:114-120, 175, 199-201]`.
- Confirming H3 (Stock Boot Overwrite): Canon Basic RAMCMP reports `r_c4 == 0` (core region overwritten by stock allocations), `r_ct == 0`, and `r_wm == 0`, with Inspector OSD displaying `WITNESS_INVALID` (Color 3,3 Light Blue), confirming stock heap allocations overwrote the witness slot `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:114-120, 173, 201-203; docs/PORT21_WITNESS_AUDIT.md:214, 230]`.

---

## 5. Hypothesis H4: Witness Record Malformed as Built

### 5.1 Hypothesis Definition and Grounding
- **Definition**: Witness record at `0x0035F7A0` was malformed as built `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:41]`.
- **Mechanism**: Struct packing bug, endianness inversion, or incorrect checksum computation producing a record that triggers inspector failure predicates P1–P6 `[VERIFIED: docs/PORT21_WITNESS_AUDIT.md:165-178]`.
- **Offline Evaluation**: DEFINITIVELY RULED OUT for code as built by host probe test `test_real_c_writer_bytes_roundtrip` in `tests/test_port21_witness_roundtrip.py` `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:41; docs/PORT21_WITNESS_AUDIT.md:16-25]`.
- **Runtime Malformation Branch**: If core survived (`r_c4 == 1`) but witness is invalid (`r_wm == 0`), the defect is isolated to runtime cache incoherence (dirty D-cache line dropped on reset before physical DRAM writeback) `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:204, 235-238; docs/PORT21_WITNESS_AUDIT.md:220-221, 231]`.

### 5.2 Next Candidate Change
- **Target File**: `chdk-port/platform/g3x/sub/110c/boot_prototype.c` `[VERIFIED: docs/PORT16_CANDIDATE_BUILD.md:107; docs/PORT21_RAM_LIFETIME.md:58-61]` and `tools/build_candidate_port2a.py` `[VERIFIED: docs/PORT16_CANDIDATE_BUILD.md:18, 107]`
- **Target Function**: `witness_record_core` and `witness_record_continuation` in `boot_prototype.c` `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:126, 133]`, and `build_candidate_loader` in `tools/build_candidate_port2a.py` `[INFERRED: docs/PORT16_CANDIDATE_BUILD.md:107; docs/PORT21_WITNESS_AUDIT.md:42]`

#### Candidate Change Details
- In candidate loader generation and restart routines, insert explicit Data Synchronization Barrier (`dsb sy`) immediately following witness field assignments `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:238; docs/PORT21_WITNESS_AUDIT.md:220-221]`.
- In candidate loader generation, add CP15 D-cache clean operation for the 32-byte witness window at `BOOT_WITNESS_ADDR` (`0x0035F7A0`) before branching to relocated core entry `0x003489B4` `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:238; docs/PORT21_WITNESS_AUDIT.md:220-221]`.
- In `chdk-port/platform/g3x/sub/110c/boot_prototype.c`, add memory barrier instructions after updating `stage_state` and recalculating `checksum` in `witness_record_core()` and `witness_record_continuation()` `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:238; docs/PORT21_RAM_LIFETIME.md:126, 133]`.
- Ensure compiler optimization in build tooling does not reorder volatile stores relative to asm cache maintenance blocks `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:238; docs/PORT21_WITNESS_AUDIT.md:220-221]`.

### 5.3 Supporting Evidence
- Host C probe using `chdk-port/platform/g3x/sub/110c/boot_witness.h` produces identical 32-byte struct with `magic=0x5749544E`, `version=0x00010001`, `stage=0x01`, `sp=0x00007FF8`, and `checksum=0x3028882D` `[VERIFIED: docs/PORT21_WITNESS_AUDIT.md:16-25, 119-138]`.
- Emulation of native inspector parser on these exact bytes returns `LOADER_REACHED` (`0x57495401`), proving format validity `[VERIFIED: docs/PORT21_WITNESS_AUDIT.md:16-25]`.
- Struct field offsets and packing match bit-for-bit with assembly parser `[VERIFIED: docs/PORT21_WITNESS_AUDIT.md:119-138; docs/PORT21_RAM_LIFETIME.md:294-295]`.
- As-built loader writer sequence records fields via volatile pointers without dedicated D-cache clean or `dsb` instructions before core handoff `[INFERRED: docs/PORT21_WITNESS_AUDIT.md:40-42, 220-221; docs/PORT21_OWNER_SESSION_PLAN.md:238]`.
- Incoherence model proves D-cache contents not written back to DRAM are lost upon reset, leaving stale memory that triggers predicate P1 (`W[0] != 0x5749544E`) `[INFERRED: docs/PORT21_WITNESS_AUDIT.md:220-221; docs/PORT21_OWNER_SESSION_PLAN.md:235-238]`.

### 5.4 Follow-Up Owner Reading
- **Physical Test Procedure**: Power on with locked card containing candidate `DISKBOOT.BIN`, reach stock Playback UI, and launch Canon Basic `extend.m` `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:97-121]`.

#### Confirming Owner Reading Outcomes
- Refuting H4 / Resolving Runtime Incoherence: Canon Basic RAMCMP reports `r_wm == 1` at `0x0035F7A0` (valid witness), with Inspector OSD displaying `LOADER_REACHED` (`0x57495401`) in Color 1,4 (White/Yellow) or `CONT_ATTEMPTED` (`0x57495404`) in Color 4,4 (Yellow/Yellow), proving witness committed cleanly to DRAM `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:116-120, 175, 199-200; docs/PORT21_WITNESS_AUDIT.md:16-25; docs/PORT16_OWNER_TRIAL_PLAN.md:217]`.
- Confirming Persistent Runtime Malformation: Canon Basic RAMCMP reports `r_c4 == 1` (core intact), but `r_wm == 0` (witness invalid in physical DRAM), with Inspector OSD displaying `WITNESS_INVALID` (`0x574954EE`) in Color 3,3 (Light Blue), indicating cache clean failure persists `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:114, 116, 120, 174, 201-204; docs/PORT21_WITNESS_AUDIT.md:220-221, 231]`.

---

## 6. Summary Table of Hypotheses, Remediation Changes, Evidence, and Confirming Readings

| Hypothesis ID & Summary | Candidate Change (File & Function) | Supporting Evidence Citations | Confirming Owner Reading (Refutation vs Confirmation) |
|:---|:---|:---|:---|
| **H1**: Binary rejected by `StartDiskboot` gate `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:38]` | `tools/build_candidate_port2a.py` (`encode_candidate_diskboot` / `encode_dancingbits_row13`) `[INFERRED: docs/PORT16_CANDIDATE_BUILD.md:18, 107; docs/PORT21_DISKBOOT_TIMING.md:51]` | Gate 1 byte 0 == 0x00 check `[VERIFIED: docs/PORT19_DISKBOOT_ENCODING.md:20-21, 153-154]`; Gate 2 non-gaonisoy `[VERIFIED: docs/PORT21_DISKBOOT_TIMING.md:128]`; reject path `0xFC05BC68` `[VERIFIED: docs/PORT21_DISKBOOT_TIMING.md:32-37]`; manifest `[VERIFIED: docs/agentbridge/PORT19_EVIDENCE_MANIFEST.json:10-17]` | **Refutes H1**: LED pulse ~1–2 s (or `r_l4 == 1` at `0x40008000` if no pulse) `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:48, 147, 191-195]`.<br>**Confirms H1**: No LED pulse, `r_l4 == 0` at `0x40008000` `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:171, 191-192]`. |
| **H2**: Loader stopped at `check_compat()` `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:39]` | `tools/build_candidate_port2a.py` (`build_candidate_loader`) `[INFERRED: docs/PORT16_CANDIDATE_BUILD.md:18, 107; docs/PORT21_RAM_LIFETIME.md:58-61]` | Platform ID `0x32A8` `[VERIFIED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:6]`; hardware address `0xFDF20270` `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:58-63]`; version `"GM1.10C"` at `0xFC54E08D` `[VERIFIED: docs/PORT18_OWNER_TRIAL_PLAN.md:22; docs/PORT19_GO_NOGO.md:47]`; `blink()` infinite loop `[INFERRED: docs/PORT21_RAM_LIFETIME.md:283-286; docs/PORT21_DISKBOOT_TIMING.md:282]` | **Refutes H2**: Reaches stock UI, Canon Basic runs `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:107-108, 195-197]`.<br>**Confirms H2**: Camera hangs with black screen/blinking LED `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:172, 195-196]`. |
| **H3**: Loader witness overwritten by stock boot `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:40]` | `chdk-port/platform/g3x/sub/110c/boot_prototype.c` (`sub_fc05b3c8_my` / `boot`) `[VERIFIED: docs/PORT16_CANDIDATE_BUILD.md:107; docs/PORT21_RAM_LIFETIME.md:118-125, 172-178]` | Stock heap `0x003489B4` spans witness `0x0035F7A0` `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:46-48]`; heap shift `new_sa = 0x00366CB0` `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:238]`; manifest `[VERIFIED: docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json:14-25]` | **Refutes H3**: `r_c4 == 1`, `r_wm == 1`, inspector shows `LOADER_REACHED` `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:175, 199-200]`.<br>**Confirms H3**: `r_c4 == 0`, `r_wm == 0`, `WITNESS_INVALID` `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:173, 201-203; docs/PORT21_WITNESS_AUDIT.md:214, 230]`. |
| **H4**: Witness malformed / runtime cache incoherence `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:41]` | `chdk-port/platform/g3x/sub/110c/boot_prototype.c` (`witness_record_core` / `witness_record_continuation`) and `tools/build_candidate_port2a.py` (`build_candidate_loader`) `[VERIFIED: docs/PORT16_CANDIDATE_BUILD.md:107; docs/PORT21_RAM_LIFETIME.md:126, 133]` | As-built struct proven valid `[VERIFIED: docs/PORT21_WITNESS_AUDIT.md:16-25]`; dirty D-cache line dropped on reset before DRAM writeback `[INFERRED: docs/PORT21_WITNESS_AUDIT.md:220-221, 231; docs/PORT21_OWNER_SESSION_PLAN.md:235-238]` | **Refutes H4 / Incoherence**: `r_wm == 1`, inspector displays `LOADER_REACHED` `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:175, 199-200; docs/PORT21_WITNESS_AUDIT.md:16-25]`.<br>**Confirms Persistent Malformation**: `r_c4 == 1` but `r_wm == 0` `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:174, 204; docs/PORT21_WITNESS_AUDIT.md:220-221, 231]`. |

---

## 7. Open UNKNOWNs to be Resolved in Later Milestones

- **U-01 (Trial O6 Card Binary Match)**: Whether the exact DISKBOOT.BIN file on the owner's card during trial O6 matched the host candidate build bit-for-bit or was corrupted `[UNKNOWN: docs/PORT21_DISKBOOT_TIMING.md:244; docs/PORT21_OWNER_SESSION_PLAN.md:38]`.
- **U-02 (Physical FAT32 Alignment Requirements)**: Whether GM1.10C ROM `StartDiskboot` requires specific FAT32 cluster alignment or multi-partition VBR layouts on physical cards `[UNKNOWN: docs/PORT21_OWNER_SESSION_PLAN.md:218; docs/PORT19_BOOTDISK_VBR.md:43-44]`.
- **U-03 (DRAM Payload Survival at `0x40008000`)**: Whether candidate payload data in uncached DRAM alias `0x40008000` survives hardware soft-restart across DIGIC 6 memory controller re-initialization (T1 vs T2 conflict) `[UNKNOWN: docs/PORT21_OWNER_SESSION_PLAN.md:44-48, 147; docs/PORT21_RAM_LIFETIME.md:221, 293; docs/PORT21_DISKBOOT_TIMING.md:298-302]`.
- **U-04 (Hardware Watchdog Reset Semantics)**: Whether an unhandled hang in `blink()` during `check_compat()` triggers a hardware watchdog reset rebooting into stock ROM `[UNKNOWN: docs/PORT21_OWNER_SESSION_PLAN.md:39; docs/PORT21_DISKBOOT_TIMING.md:251, 282]`.
- **U-05 (Stock Boot Overwrite Timing and Writer)**: The exact ROM instruction and execution timing that overwrites `0x003489B4` or `0x0035F7A0` in stock boot before Canon Basic execution `[UNKNOWN: docs/PORT21_OWNER_SESSION_PLAN.md:40; docs/PORT21_RAM_LIFETIME.md:47, 247-249, 269, 290]`.
- **U-06 (Palette Index 3 Physical LCD Colour)**: Whether palette index 3 renders as red or light blue on the physical G3 X LCD panel under active palette `0x00015DB4` `[UNKNOWN: docs/PORT21_WITNESS_AUDIT.md:248-250]`.
- **U-07 (Soft-Restart CPU Mode and Vector Table)**: The exact CPU mode (Supervisor vs System) and exception vector configuration during early boot restart in `boot()` `[UNKNOWN: docs/PORT21_OWNER_SESSION_PLAN.md:228; docs/PORT21_RAM_LIFETIME.md:109-125]`.
- **U-08 (Unverified Runtime Hook Preconditions U1–U3)**: The verified ROM addresses and instruction prologues for GM1.10C `CreateTask` (U1), `InitFileModules` (U2), and `task_PhySw` (U3) `[UNKNOWN: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:1-50]`.
- **U-09 (Platform ID Hardware Address / Value `0xFDF20270`)**: The physical MMIO register or ROM address for verifying Platform ID `0x32A8` in the loader before `boot()` (previously hypothesized as `0xFDF20270`) does not appear in any PORT16–PORT21 document or manifest and remains `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:58-63]`.
