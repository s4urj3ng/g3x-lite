# PORT-22 T2: Remediation Design per Hypothesis H1–H4 (Research, No ROM Reads)

Labels: `[VERIFIED]` means the cited lines state the fact. `[INFERRED]` means reasoning from cited facts, including every proposed change in this document. A proposal is never `[VERIFIED]`. `[UNKNOWN]` means no PORT16–PORT21 doc or evidence manifest settles it. No value is guessed for an `[UNKNOWN]` item. This document read no ROM range and no binary, and it commits no binary.

- **Target firmware**: PowerShot G3 X GM1.10C, Platform ID `0x32A8` (12968) `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:3; docs/PORT16_FIRSTBOOT_U_TRIAGE.md:6]`.
- **CPU core**: `docs/PORT21_WITNESS_AUDIT.md:131` names Cortex-R4. `docs/PORT16_FIRSTBOOT_U_TRIAGE.md:6` records a conflict between Cortex-A9 and Cortex-R4 annotations in tracked files. The core type and the CPU mode at each boot stage are therefore `[UNKNOWN: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:6; docs/PORT21_WITNESS_AUDIT.md:131]` (U-09).
- **Scope**: Phase 0 offline design only. No firmware flashing, camera operation, card write or hardware trial is done or authorised by this document `[VERIFIED: docs/PORT18_OWNER_TRIAL_PLAN.md:5; docs/PORT21_OWNER_SESSION_PLAN.md:5]`.

---

## 1. Source of the Hypotheses and Shared Preconditions

- **Hypothesis source**: H1–H4 are defined in the PORT-21 T4 plan, `docs/PORT21_OWNER_SESSION_PLAN.md:34-41`. Each section below quotes its row `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:34-41]`.
- **Inspector-address alternative comes first**: the tracked inspector payload reads `0x0035F780`, and only the regenerated payload reads `0x0035F7A0`. Which one ran during O6 is unknown, so the owner checks the card's `WITNESS.BIN` SHA-256 before any H1–H4 reading is interpreted `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:42, 63-70; docs/PORT21_WITNESS_AUDIT.md:93-95]`.
- **Untracked loader sources**: `chdk-port/loader/g3x/main_prototype.c` and `chdk-port/loader/generic/check_compat.c` are not tracked. They are named below as change locations without line citations. Tracked docs describe their behaviour only as `[INFERRED]` `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:59; docs/PORT18_OWNER_TRIAL_PLAN.md:9]`.
- **Loader disassembly record**: tracked doc `docs/PORT20_LED_CANDIDATE.md` records pinned-objdump disassembly of the built loader, with symbols `check_pid`, `check_compat`, `blink`, `set_led` and `my_restart`. This is the tracked evidence for the loader functions named below `[VERIFIED: docs/PORT20_LED_CANDIDATE.md:105-135, 254-265]`.

---

## 2. Hypothesis H1: `StartDiskboot` Never Reached the Loader

### 2.1 Hypothesis Definition
- **Definition**: "`StartDiskboot` never reached loader (ROM rejected binary or skipped loading)", offline verdict FITS / UNTESTED `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:38]`.
- **Reject path**: if `sub_fc54de38` fails Gate 1 (byte 0 not zero, `0xFC54DE3C`) or Gate 2 (`gaonisoy` match, `0xFC54DE4C`), `StartDiskboot` prints "not executable" at `0xFC05BC68`, frees the buffer at `0xFC05BC70` and returns to `task_Startup` at `0xFC05BC38` without running the loader `[VERIFIED: docs/PORT21_DISKBOOT_TIMING.md:32-38; docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json:215]`.
- **Skip path**: if the `BOOTDISK` VBR marker is missing, `StartDiskboot` returns before reading the file `[VERIFIED: docs/PORT21_DISKBOOT_TIMING.md:105-107]`. The docs give conflicting marker offsets: `0x40` (FAT16) or `0x52` (FAT32) in one place, and `0x1E0` on FAT32 or `0x40` on FAT12/FAT16 in another. Which is correct is `[UNKNOWN: docs/PORT21_DISKBOOT_TIMING.md:106; docs/PORT18_OWNER_TRIAL_PLAN.md:230]` (U-03).
- **Timing**: the reject path still reads all 118,001 bytes from the card, so "slower only when locked" does not rule out H1 `[INFERRED: docs/PORT21_DISKBOOT_TIMING.md:22-30]`.

### 2.2 Next Candidate Change
- **Target File**: `tools/build_candidate_port2a.py` `[VERIFIED: docs/PORT19_DISKBOOT_ENCODING.md:27; tools/build_candidate_port2a.py:601]`
- **Target Function**: `encode_candidate_diskboot()` in `tools/build_candidate_port2a.py`, which writes `DISKBOOT.BIN` `[VERIFIED: tools/build_candidate_port2a.py:601; docs/PORT16_CANDIDATE_BUILD.md:107]`
- **Proposal H1-C1**: add fail-closed assertions after encoding that mirror the two ROM gates: byte 0 is zero, and the words at offsets 16 and 32 are not "gaon"/"isoy". These are the same checks as the host command in the PORT-21 timing doc `[INFERRED: docs/PORT21_DISKBOOT_TIMING.md:52-56, 127-128]`. This is a regression guard, not a fix. No PORT16–PORT21 doc records an encoding defect, and the current build already passes these checks on the host `[VERIFIED: docs/PORT21_DISKBOOT_TIMING.md:56-57]`.
- **Scope note**: H1-C1 changes no ROM-facing value. Whether the GM1.10C reader needs any header field, parameter or card layout beyond the two gates and the `BOOTDISK` marker is `[UNKNOWN: docs/PORT21_DISKBOOT_TIMING.md:58; docs/PORT21_OWNER_SESSION_PLAN.md:218]` (U-02).

### 2.3 Supporting Evidence
- Gate 1 and Gate 2 live in `sub_fc54de38` (`0xFC54DE38`), and the reject branch skips the shift loop, decoder, cache/MPU setup and copy to `0x40008000` `[VERIFIED: docs/PORT21_DISKBOOT_TIMING.md:34-38, 127-128; docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json:215]`.
- The host candidate (SHA-256 `9468257364…`) passes both static gates `[VERIFIED: docs/PORT21_DISKBOOT_TIMING.md:51-56]`. That it passes them in ROM is `[INFERRED: docs/PORT21_DISKBOOT_TIMING.md:57]`.
- Whether the file on the owner's card during O6 matched the host build is `[UNKNOWN: docs/PORT21_DISKBOOT_TIMING.md:58, 244]` (U-01).

### 2.4 Follow-Up Owner Reading
- **Pre-power-on reading**: the owner computes the SHA-256 of `DISKBOOT.BIN` on the card and compares it with the build manifest (`9468257364…` default, `757dfb7f…` LED build). A mismatch confirms a card-file cause for H1 without powering on `[INFERRED: docs/PORT21_DISKBOOT_TIMING.md:244; docs/PORT20_LED_CANDIDATE.md:68, 71]`.
- **Refuting H1**: a PORT-20 LED change of state for about 1–2 s at power-on with the card locked shows the loader entry ran `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:185, 195; docs/PORT20_LED_CANDIDATE.md:157-161]`. LED polarity is `[UNKNOWN: docs/PORT20_LED_CANDIDATE.md:160]`, so the owner looks for any change, not "on".
- **Confirming H1**: no LED change, a normal-speed stock UI, and RAMCMP `r_l4 == 0` at `0x40008000` `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:171, 187-192]`. `r_l4` survival after a reboot is `[UNKNOWN: docs/PORT21_OWNER_SESSION_PLAN.md:44-48, 147]` (U-04), so `r_l4` only counts together with the LED reading.

---

## 3. Hypothesis H2: Loader Ran but Stopped at `check_compat()`

### 3.1 Hypothesis Definition
- **Definition**: "Loader ran, but stopped at `check_compat()`", verdict RULED OUT for uninterrupted execution and UNTESTED for a watchdog reset `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:39]`.
- **Mechanism**: a platform ID or version mismatch calls `blink()`, which loops forever `[INFERRED: docs/PORT21_RAM_LIFETIME.md:275, 284; docs/PORT21_DISKBOOT_TIMING.md:248]`. Whether a watchdog then resets into stock ROM is `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:286; docs/PORT21_DISKBOOT_TIMING.md:251]` (U-05).

### 3.2 Next Candidate Change
- **Target File**: `chdk-port/loader/generic/check_compat.c` (untracked; named in tracked docs) `[INFERRED: docs/PORT21_RAM_LIFETIME.md:59; docs/PORT21_DISKBOOT_TIMING.md:248]`
- **Target Function**: `blink()` and the failure branch of `check_compat()` in `chdk-port/loader/generic/check_compat.c`. Both are present in the built loader `[VERIFIED: docs/PORT20_LED_CANDIDATE.md:122-129, 260, 263]`.
- **No defect to fix**: no PORT16–PORT21 doc shows a wrong platform ID or version comparison. `check_pid` compares two halfwords. It reads one through a pointer at table offset `0x210` and the other at offset `0x214`, and `check_compat` passes table words at `0x218`/`0x21c` to `ver_cmp` `[VERIFIED: docs/PORT20_LED_CANDIDATE.md:113-129]`. The table base, the address the pointer holds (the platform-ID source) and the expected values are not recorded in any doc `[UNKNOWN: docs/PORT20_LED_CANDIDATE.md:113-129]` (U-06). So this plan does not change the comparison.
- **Proposal H2-D1 (host diagnostic, before any code change)**: read the `check_pid`/`check_compat` table words from the host-built `candidate_loader.elf` with the pinned objdump. This uses the same method as the PORT-20 disassembly and reads a build artifact, not the ROM. The goal is to record the expected platform ID (compare to `0x32A8`), the version operands and the platform-ID source address `[INFERRED: docs/PORT20_LED_CANDIDATE.md:103-107, 113-129; docs/PORT21_RAM_LIFETIME.md:3]`. This resolves U-06 without guessing.
- **Proposal H2-C1 (make the failure observable)**: change `blink()` so the compatibility-failure loop drives the PORT-20 LED register `0xD20B0884` with the verified action values `0x004D0002`/`0x004C0003` in a repeating pattern. The pattern must differ from the single entry pulse of `loader_entry_led.S` `[INFERRED: docs/PORT20_LED_CANDIDATE.md:14-16, 31-37, 161]`. Today the docs cannot say whether `blink()` drives that LED at all `[UNKNOWN: docs/PORT21_OWNER_SESSION_PLAN.md:172]` (U-07). Which register `set_led`/`blink` currently write is also unrecorded `[UNKNOWN: docs/PORT20_LED_CANDIDATE.md:258, 260]` (U-07).

### 3.3 Supporting Evidence
- In the built loader, `my_restart` calls `check_compat` first, and `check_compat` calls `check_pid` and then `ver_cmp` `[VERIFIED: docs/PORT20_LED_CANDIDATE.md:122-134]`.
- The LED register and action values are verified, and their polarity is unknown `[VERIFIED: docs/PORT20_LED_EVIDENCE.md:292; docs/PORT20_LED_CANDIDATE.md:14-16]`.
- An uninterrupted `blink()` loop cannot reach the stock UI reported in O6 `[INFERRED: docs/PORT21_RAM_LIFETIME.md:283-286]`.

### 3.4 Follow-Up Owner Reading
- **Refuting H2**: after the entry pulse the camera reaches the stock Playback UI and `extend.m` runs `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:143, 195-197]`. With H2-C1 built in, the failure pattern is absent `[INFERRED: docs/PORT20_LED_CANDIDATE.md:161]`.
- **Confirming H2**: the entry pulse, then the repeating H2-C1 failure pattern and a hang before the stock UI. The owner stops after 10 s with no response and follows the recovery plan `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:172, 196, 246, 258-262]`. Without H2-C1, a hang after the pulse fits H2 but does not separate it from a later core hang `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:196]`.

---

## 4. Hypothesis H3: Loader Wrote the Witness, Stock Boot Overwrote It

### 4.1 Hypothesis Definition
- **Definition**: "Loader wrote witness, but stock boot later overwrote `0x0035F7A0`", verdict FITS / UNTESTED `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:40]`.
- **Mechanism**: the stock heap `[0x003489B4, 0x00600014)` contains `0x0035F7A0`, so stock boot MAY reuse the witness slot `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:243-246]`. No writer was identified, and whether the slot is overwritten before Canon Basic runs is `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:247, 290]` (U-08). A failed heap shift sends control to stock boot only through a fault or reset into `0xFC02000C`, and none was identified `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:270, 289]` (U-08).

### 4.2 Next Candidate Change
- **Target File**: `chdk-port/platform/g3x/sub/110c/boot_prototype.c` (tracked) `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:116, 132]`
- **Target Function**: `boot()` and `sub_fc05b3c8_my()` in `chdk-port/platform/g3x/sub/110c/boot_prototype.c`, plus `task_Startup_my()` for H3-C1 `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:107, 116, 125-129]`
- **What H3 work is**: the PORT-21 work item is to debug calls that already exist and are evidenced. It does not add new cache or MPU calls `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:228]`. The two cache facts in the docs are:
  - (a) `boot()` already calls `sub_fc127a62` to clean the full L1 data cache after the High RAM copy (`0x010E1000`, size `0x26D00`) `[VERIFIED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:56]`.
  - (b) The H3 work item names `0xFC0D9CAC` for cache clean/invalidate and `0xFC0D9CB0` for MPU Region 7 `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:228]`. Those two addresses are ROM call sites in `sub_fc0d9c9c` (`0xFC0D9C9C`) on the `StartDiskboot` accept path, which runs before the loader. They are not in `boot()` `[VERIFIED: docs/PORT21_DISKBOOT_TIMING.md:153-156; docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json:275]`.
  - The sources do not say which of (a) or (b) the H3 work item means for the soft restart `[UNKNOWN: docs/PORT21_OWNER_SESSION_PLAN.md:228; docs/PORT16_FIRSTBOOT_U_TRIAGE.md:56]` (U-10).
- **Proposal H3-D1 (host diagnostic)**: check from the host-built `candidate_main.elf` disassembly that the existing `sub_fc127a62` call in `boot()` gets the documented arguments, and that `sub_fc05b3c8_my` stores `new_sa` (`0x00366CB0`) at `sp[0x08]` before `blx sub_fc31b408` `[INFERRED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:56; docs/PORT21_RAM_LIFETIME.md:119-121]`. The stack frame needs no change: the `0x78` (120-byte) frame is already a multiple of 8, and no PORT-21 doc records an alignment defect `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:118]`.
- **Proposal H3-C1 (completion marker that survives an overwrite)**: in `task_Startup_my()`, after `witness_record_continuation()`, emit a second PORT-20 LED pulse on `0xD20B0884` `[INFERRED: docs/PORT21_RAM_LIFETIME.md:125-129; docs/PORT20_LED_CANDIDATE.md:31-37]`. An LED pulse is still visible if stock memory later overwrites the witness, so the owner can tell "core path completed" apart from "faulted into stock boot". Whether an MMIO write is safe at that point in DryOS is `[UNKNOWN: docs/PORT20_LED_CANDIDATE.md:16, 160]` (U-07).
- **Not proposed**: moving the witness outside the stock heap. No PORT16–PORT21 doc identifies a RAM range that is free of stock writers. That target range is `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:47, 248]` (U-08).

### 4.3 Supporting Evidence
- Stock heap base `0x003489B4` and upper bound `0x00600014`, read from ROM literal pools `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:165-169; docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json:16]`.
- The candidate shifts the heap base to `0x00366CB0`, above the witness `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:183, 233]`.
- `boot()` replays the stock copy loops and zeroes Canon BSS up to `0x003489B4`, and does not touch the witness `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:113-114, 235]`.

### 4.4 Follow-Up Owner Reading
- **Refuting H3**: `r_c4 == 1` at `0x003489B4` and `r_wm == 1` at `0x0035F7A0`, with the inspector showing `LOADER_REACHED` or `CONT_ATTEMPTED` `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:114-120, 175, 199-200]`. With H3-C1 built in, the second pulse is also seen `[INFERRED: docs/PORT20_LED_CANDIDATE.md:161]`.
- **Confirming H3**: entry pulse, stock UI, `r_c4 == 0`, `r_wm == 0`, `WITNESS_INVALID` `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:173, 201-203]`. If H3-C1 is built in, a missing second pulse points to a fault before `task_Startup_my()` completed `[INFERRED: docs/PORT21_RAM_LIFETIME.md:125-129]`.

---

## 5. Hypothesis H4: Witness Record Malformed as Built

### 5.1 Hypothesis Definition
- **Definition**: "Witness record at `0x0035F7A0` was malformed as built", verdict RULED OUT for the as-built code by an offline host test `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:41]`.
- **Ruled-out format bug**: a struct packing, endianness or checksum bug would be a format bug. T3 found no writer/parser mismatch, and the as-built record parses as `LOADER_REACHED` (`0x57495401`) at its own address `[VERIFIED: docs/PORT21_WITNESS_AUDIT.md:24-25, 138, 231]`. The parser predicates P1–P6 only define when `WITNESS_INVALID` (`0x574954EE`) is returned. They are not evidence of a format bug `[VERIFIED: docs/PORT21_WITNESS_AUDIT.md:165-178]`.
- **What remains (runtime variant)**: the T4 branch "`r_c4 == 1`, `r_wm == 0`" is read as a possible runtime cause, such as a write not visible to the reader or a fault mid-write `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:235-236; docs/PORT21_WITNESS_AUDIT.md:215-221, 231]`.

### 5.2 Next Candidate Change
- **Target File**: `chdk-port/loader/g3x/main_prototype.c` (untracked; named in tracked docs) `[INFERRED: docs/PORT21_RAM_LIFETIME.md:59; docs/PORT21_WITNESS_AUDIT.md:39-41]` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c` (tracked) `[VERIFIED: docs/PORT21_WITNESS_AUDIT.md:49-54]`
- **Target Function**: `my_restart()` in `chdk-port/loader/g3x/main_prototype.c`, and `witness_record_core()` / `witness_record_continuation()` in `chdk-port/platform/g3x/sub/110c/boot_prototype.c` `[VERIFIED: docs/PORT21_WITNESS_AUDIT.md:41, 53-54]`
- **Premise as the sources state it**: `my_restart()` writes the witness before cache synchronisation and before the branch to `0x003489B5` `[VERIFIED: docs/PORT21_WITNESS_AUDIT.md:41]`. The loader's cache maintenance (D-cache clean/invalidate, I-cache invalidate, `cpsid if`) is described in tracked docs only as `[INFERRED]` behaviour. The helper constants recorded are `0xFC127AB1` (DCCISW) and `0xFC127B09` (ICIALLU) `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:71-73, 276]`. The built `my_restart` contains `cpsid if` (disassembly line `823c`) `[VERIFIED: docs/PORT20_LED_CANDIDATE.md:150]`. The inspector script flushes L1 caches (`0xFC127A85`, `0xFC127B2B`) before it reads `[VERIFIED: docs/PORT21_WITNESS_AUDIT.md:59]`.
- **Open premise**: whether the existing loader sync covers the 32-byte witness window at `0x0035F7A0`, and whether the core writers are followed by any cache clean, is `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:72-73; docs/PORT21_WITNESS_AUDIT.md:220]` (U-11).
- **Proposal H4-D1 (host diagnostic, resolves U-11)**: from the host-built `candidate_loader.elf`, disassemble `my_restart` (`0x000081D8` default build) from the last witness store to the terminal branch. Record whether the DCCISW helper is called after the stores, and over which sets/ways. Do the same for the two core writers in `candidate_main.elf` `[INFERRED: docs/PORT20_LED_CANDIDATE.md:103-107, 265; docs/PORT21_RAM_LIFETIME.md:73]`.
- **Proposal H4-C1 (only if H4-D1 shows a gap)**: add a clean-by-address of the witness window plus a `dsb` after the witness stores in `my_restart()`, and after the checksum update in `witness_record_core()` / `witness_record_continuation()` `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:238; docs/PORT21_WITNESS_AUDIT.md:220-221]`. If H4-D1 shows that the existing sync already covers the window, H4-C1 is dropped. The cache line size and the encoding of the clean operation for this core are `[UNKNOWN: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:6]` (U-09).

### 5.3 Supporting Evidence
- A host C probe built from the real `boot_witness.h` gives `magic=0x5749544E`, checksum `0x3028882D`, and parses as `LOADER_REACHED` `[VERIFIED: docs/PORT21_WITNESS_AUDIT.md:16-23]`.
- A completed `core_copy()` zeroes the slot before the eight witness stores. A prior record survives into a partial write only if `core_copy()` did not complete or the stores reached cache but not DRAM, and both are unknown `[VERIFIED: docs/PORT21_WITNESS_AUDIT.md:48, 220]`.
- The core writers move `stage_state` from `0x01` to `0x03` to `0x07` and recompute the checksum `[VERIFIED: docs/PORT21_WITNESS_AUDIT.md:53-54]`.

### 5.4 Follow-Up Owner Reading
- **Refuting the runtime variant**: `r_c4 == 1` and `r_wm == 1`, with `LOADER_REACHED` or `CONT_ATTEMPTED` on the inspector `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:175, 199-200, 230-231]`.
- **Confirming the runtime variant**: after H4-C1, still `r_c4 == 1` with `r_wm == 0` and `WITNESS_INVALID`. That points away from cache writeback and toward a fault mid-write or another writer `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:201-204; docs/PORT21_WITNESS_AUDIT.md:215-222]`.

---

## 6. Summary Table

| Hypothesis ID & Summary | Candidate Change (File & Function) | Supporting Evidence | Confirming Owner Reading |
|:---|:---|:---|:---|
| **H1**: loader never reached (reject or skip) `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:38]` | H1-C1 gate-mirror assertions in `encode_candidate_diskboot()`, `tools/build_candidate_port2a.py` (regression guard only) `[INFERRED: docs/PORT21_DISKBOOT_TIMING.md:52-56]` | ROM gates and reject path `[VERIFIED: docs/PORT21_DISKBOOT_TIMING.md:32-38]`; host build passes gates `[VERIFIED: docs/PORT21_DISKBOOT_TIMING.md:56]` | Card SHA-256 check, then no LED change plus `r_l4 == 0` confirms; an LED change refutes `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:187-192]` |
| **H2**: stopped in `check_compat()` `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:39]` | H2-D1 host read of compat table; H2-C1 distinct LED pattern in `blink()`, `chdk-port/loader/generic/check_compat.c` (untracked) `[INFERRED: docs/PORT20_LED_CANDIDATE.md:113-129, 161]` | Call order `my_restart` → `check_compat` → `check_pid`/`ver_cmp` `[VERIFIED: docs/PORT20_LED_CANDIDATE.md:122-134]`; LED register `[VERIFIED: docs/PORT20_LED_EVIDENCE.md:292]` | Entry pulse, then failure pattern and hang, confirms; stock UI with no pattern refutes `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:195-197]` |
| **H3**: witness overwritten by stock boot `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:40]` | H3-D1 host check of the existing `sub_fc127a62` call and heap shift in `boot()` / `sub_fc05b3c8_my()`; H3-C1 second LED pulse in `task_Startup_my()`, `boot_prototype.c` `[INFERRED: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:56; docs/PORT21_RAM_LIFETIME.md:119-129]` | Stock heap covers witness `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:243-246]`; shifted heap base `[VERIFIED: docs/PORT21_RAM_LIFETIME.md:183]` | `r_c4 == 0`, `r_wm == 0`, `WITNESS_INVALID` confirms; `r_c4 == 1`, `r_wm == 1` refutes `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:173, 175, 199-203]` |
| **H4**: malformed as built (format bug ruled out; runtime variant open) `[VERIFIED: docs/PORT21_OWNER_SESSION_PLAN.md:41]` | H4-D1 host disassembly of the `my_restart()` sync; H4-C1 witness-window clean only if a gap is found, `main_prototype.c` (untracked) / `boot_prototype.c` `[INFERRED: docs/PORT21_WITNESS_AUDIT.md:41, 220-221]` | No writer/parser mismatch `[VERIFIED: docs/PORT21_WITNESS_AUDIT.md:25, 138]`; witness written before cache sync `[VERIFIED: docs/PORT21_WITNESS_AUDIT.md:41]` | `r_c4 == 1`, `r_wm == 0` after H4-C1 confirms the runtime variant; `r_wm == 1` refutes `[INFERRED: docs/PORT21_OWNER_SESSION_PLAN.md:199-204]` |

---

## 7. Open UNKNOWNs (to be resolved in a later milestone)

- **U-01**: whether the `DISKBOOT.BIN` on the O6 card matched the host build `[UNKNOWN: docs/PORT21_DISKBOOT_TIMING.md:58, 244]`.
- **U-02**: whether the GM1.10C reader needs anything beyond the two gates and the `BOOTDISK` marker (header fields, card layout) `[UNKNOWN: docs/PORT21_OWNER_SESSION_PLAN.md:218; docs/PORT21_DISKBOOT_TIMING.md:58]`.
- **U-03**: the correct `BOOTDISK` marker offset per filesystem; two tracked docs disagree `[UNKNOWN: docs/PORT21_DISKBOOT_TIMING.md:106; docs/PORT18_OWNER_TRIAL_PLAN.md:230]`.
- **U-04**: whether loader data at the uncached alias survives a reboot (T1 vs T2 conflict over `r_l4`) `[UNKNOWN: docs/PORT21_OWNER_SESSION_PLAN.md:44-48; docs/PORT21_RAM_LIFETIME.md:221; docs/PORT21_DISKBOOT_TIMING.md:298-302]`.
- **U-05**: whether a watchdog or fault reset follows a `blink()` hang `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:286; docs/PORT21_DISKBOOT_TIMING.md:251]`.
- **U-06**: the platform-ID source address, the compat table base and the expected values `check_pid`/`ver_cmp` compare. No value is recorded in PORT16–PORT21 docs or manifests `[UNKNOWN: docs/PORT20_LED_CANDIDATE.md:113-129; docs/PORT21_RAM_LIFETIME.md:59-63]`.
- **U-07**: which LED register `blink()`/`set_led` currently drive, and whether an MMIO LED write is safe from DryOS task context `[UNKNOWN: docs/PORT21_OWNER_SESSION_PLAN.md:172; docs/PORT20_LED_CANDIDATE.md:160, 258-260]`.
- **U-08**: any stock writer that covers the witness before Canon Basic runs, any fault or reset path into stock ROM, and any RAM range free of stock writers `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:47, 247-248, 289-290]`.
- **U-09**: CPU core type, CPU mode during `boot()`, cache line size and the cache-clean encoding for this core `[UNKNOWN: docs/PORT16_FIRSTBOOT_U_TRIAGE.md:6; docs/PORT21_OWNER_SESSION_PLAN.md:228]`.
- **U-10**: which cache routine the H3 work item refers to: the `sub_fc127a62` call in `boot()` or the ROM accept-path call site in `sub_fc0d9c9c` `[UNKNOWN: docs/PORT21_OWNER_SESSION_PLAN.md:228; docs/PORT16_FIRSTBOOT_U_TRIAGE.md:56; docs/PORT21_DISKBOOT_TIMING.md:155]`.
- **U-11**: whether the existing loader cache sync covers the witness window, and whether the core witness writers are followed by any cache clean `[UNKNOWN: docs/PORT21_RAM_LIFETIME.md:72-73; docs/PORT21_WITNESS_AUDIT.md:41, 220]`.
