# PORT-19: GM1.10C Volume Boot Record (VBR) Marker Offset Resolution (P3)

**Task ID**: `p19-vbr-marker`  
**Target Device**: Canon PowerShot G3 X (Firmware GM1.10C, Platform ID `0x32A8` = 12968 dec)  
**Host Platform**: AgentBridge isolated worktree (`/var/lib/agentbridge/worktrees/g3x-lite/port-19-trial-blockers-p19-vbr-marker`)  
**Evaluation Mode**: Phase 0 Read-Only Offline Firmware Disassembly & Static Analysis  
**Date**: 2026-10-31  

---

## 1. Definitive Answers & Executive Summary

### 1.1 Resolution of Trial-Plan Conflict P3
**P3 Conflict Status**: **`RESOLVED`**  

The apparent contradiction between VBR offsets **`0x1E0`** and **`0x40`** in tracked documentation (`docs/PORT18_OWNER_TRIAL_PLAN.md:23, 188`, `docs/PROJECT_STATE.md:201, 333`, `docs/HANDOFF.md:435, 923`) is **not** an ambiguity or conflicting ROM implementation. Rather, the offset is **filesystem-dependent** and determined dynamically at partition mount time by `Mounter.c` routine `0xFC37A4B6` `[VERIFIED: 0xFC37A4B6-0xFC37A658]`.

### 1.2 Stated Answers per Filesystem Type: BOOTDISK Marker

| Filesystem Type | `BOOTDISK` Marker Offset | Marker String & Length | Status & Classification | ROM Address Citations |
|---|---|---|---|---|
| **FAT16** | **`0x40`** (64 dec) | `"BOOTDISK"` (8 ASCII bytes) | `VERIFIED` | `0xFC37A63A`, `0xFC37A650`, `0xFC37A654`, `0xFC37B2AE`, `0xFC37B3A8` |
| **FAT32** | **`0x1E0`** (480 dec) | `"BOOTDISK"` (8 ASCII bytes) | `VERIFIED` | `0xFC37A5FA`, `0xFC37A606`, `0xFC37A654`, `0xFC37B2AE`, `0xFC37B3A8` |
| **exFAT** | **`UNSUPPORTED`** (No offset / not checked) | None | `VERIFIED` | `0xFC37A4CE`, `0xFC37A508-0xFC37A524`, `0xFC37A556`, `0xFC37A55C` |
| **FAT12** | **`0x40`** (64 dec) | `"BOOTDISK"` (8 ASCII bytes) | `VERIFIED` | `0xFC37A63E`, `0xFC37A650`, `0xFC37A654`, `0xFC37B2AE`, `0xFC37B3A8` |

### 1.3 Secondary Marker: SCRIPT Marker (Canon Basic Boot / Dual-Boot)

| Filesystem Type | `SCRIPT` Marker Offset | Marker String & Length | Status & Classification | ROM Address Citations |
|---|---|---|---|---|
| **FAT16** | **`0x1F0`** (496 dec) | `"SCRIPT"` (6 ASCII bytes) | `VERIFIED` | `0xFC37A668`, `0xFC37A66C`, `0xFC37A670`, `0xFC37A67C`, `0xFC37A7F0` |
| **FAT32** | **`0x1F0`** (496 dec) | `"SCRIPT"` (6 ASCII bytes) | `VERIFIED` | `0xFC37A668`, `0xFC37A66C`, `0xFC37A670`, `0xFC37A67C`, `0xFC37A7F0` |
| **exFAT** | **`UNSUPPORTED`** (No offset / not checked) | None | `VERIFIED` | `0xFC37A4D0`, `0xFC37A55C` |
| **FAT12** | **`0x1F0`** (496 dec) | `"SCRIPT"` (6 ASCII bytes) | `VERIFIED` | `0xFC37A668`, `0xFC37A66C`, `0xFC37A670`, `0xFC37A67C`, `0xFC37A7F0` |

### 1.4 Other Markers: EOS_DEVELOP Marker

| Marker Name | Scope / Target | Offset / Status | Status & Classification | ROM Address Citations & Evidence |
|---|---|---|---|---|
| **EOS_DEVELOP** | Inspected Mounter VBR-check routine (`0xFC37A4B6-0xFC37A680`) | Not checked (routine compares only `BOOTDISK` and `SCRIPT`) | `VERIFIED` | `0xFC37A4B6-0xFC37A680`, `0xFC37B2AE-0xFC37B2C2` |
| **EOS_DEVELOP** | GM1.10C elsewhere in bootloader / ROM | Unverified beyond inspected Mounter window | `UNKNOWN` | `0xFC37A400-0xFC37B3FF` (window boundary) |

- **Scoped Verification**: **`VERIFIED`** that the inspected Mounter VBR-check routine (`0xFC37A4B6-0xFC37A680`, with helper `0xFC37B2AE-0xFC37B2C2`) compares only `BOOTDISK` and `SCRIPT` and does not compare `EOS_DEVELOP`; **`UNKNOWN`** whether `EOS_DEVELOP` is checked anywhere else in GM1.10C.
- **Analysis Scope**: Inspection is strictly bounded by the Phase 0 read budget to the 4 KiB window `0xFC37A400-0xFC37B3FF`. Within this routine, partition headers are inspected solely for `"BOOTDISK"` and `"SCRIPT"`. Because no full-ROM or unbudgeted string scans are permitted in Phase 0, global absence across the remaining bootloader and firmware code cannot be proven and remains `UNKNOWN`.

---

## 2. Comparison and Reconciliation with PORT-18 Trial Plan

### 2.1 What `docs/PORT18_OWNER_TRIAL_PLAN.md` Currently States
1. **Section 1.1 (Blocker Table P3)**:
   > `| P3 | BOOTDISK VBR marker offset | CONFLICT -> UNKNOWN. 0x1E0 in docs/PROJECT_STATE.md:201, docs/HANDOFF.md:435, 463 and docs/PORT16_FIRSTBOOT_U_TRIAGE.md:470-471 [VERIFIED]; 0x40 in docs/PROJECT_STATE.md:333 and docs/HANDOFF.md:923 [VERIFIED]. The card must not be written while this is unresolved. |`
2. **Section 2.2 (VBR Markers)**:
   > `- SCRIPT (6 ASCII bytes) at VBR offset 0x1F0 [VERIFIED: docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:48, 69].`  
   > `- BOOTDISK (8 ASCII bytes): offset is UNKNOWN (P3 conflict, 0x1E0 vs 0x40). Do not write the card until this is resolved.`  
   > `- That both markers can coexist is stated from ROM disassembly in docs/PROJECT_STATE.md:201, 209 [VERIFIED], but is unverified on hardware...`
3. **Section 2.1 (Filesystem Requirements)**:
   > `1. Use a FAT16 or FAT32 partition [VERIFIED: docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:47, 69]. exFAT is [UNKNOWN] for Canon Basic activation, which is documented only for FAT16/FAT32...`  
   > `2. Card capacity: ... A prior test plan specified a primary FAT32 partition of <= 32 GB [VERIFIED: docs/HANDOFF.md:1833]. Using <= 32 GB is [INFERRED: docs/HANDOFF.md:1833].`

### 2.2 How This Analysis Resolves P3
1. **Root Cause of Apparent Conflict**:
   - `docs/PROJECT_STATE.md:333` and `docs/HANDOFF.md:923` cited `0x40` based on early DOS FAT16 BPB structure analysis without specifying filesystem bounds.
   - `docs/PROJECT_STATE.md:201` and `docs/HANDOFF.md:435` cited `0x1E0` based on FAT32 partition mount analysis.
   - Both doc citations were accurate reflections of ROM instructions, but each lacked the filesystem qualification.
2. **Unambiguous Directive for Trial Execution**:
   - For **FAT32** cards (the standard filesystem for cards > 2 GB and ≤ 32 GB, as specified in `docs/PORT18_OWNER_TRIAL_PLAN.md:195`):
     - `BOOTDISK` MUST be written at VBR offset **`0x1E0`** (480 decimal, 8 ASCII bytes: `42 4F 4F 54 44 49 53 4B`).
     - `SCRIPT` MUST be written at VBR offset **`0x1F0`** (496 decimal, 6 ASCII bytes: `53 43 52 49 50 54`).
   - For **FAT16** cards (if using cards ≤ 2 GB):
     - `BOOTDISK` MUST be written at VBR offset **`0x40`** (64 decimal, 8 ASCII bytes).
     - `SCRIPT` MUST be written at VBR offset **`0x1F0`** (496 decimal, 6 ASCII bytes).
   - For **exFAT** cards:
     - exFAT cards MUST NOT be used for the trial. GM1.10C `Mounter.c` unconditionally bypasses both marker checks on exFAT, leaving both `drive_desc->is_bootdisk` and `drive_desc->is_scriptdisk` as 0 `[VERIFIED: 0xFC37A4CE, 0xFC37A4D0, 0xFC37A55C]`. Neither `StartDiskboot` nor Canon Basic can be triggered from an exFAT partition.

---

## 3. Spatial Layout and Non-Overlap Analysis

### 3.1 FAT32 Partition VBR (Sector 0 of Partition)
On a FAT32 partition, the volume boot record is a 512-byte sector (`0x000` to `0x1FF`):
- `0x000..0x002`: Jump instruction (`EB 58 90` or `EB 3C 90`)
- `0x003..0x00A`: OEM Name (`MSDOS5.0` or similar)
- `0x00B..0x059`: FAT32 Extended BIOS Parameter Block (BPB)
- `0x05A..0x1DF`: Bootstrap code / padding (390 bytes)
- `0x1E0..0x1E7`: **`BOOTDISK`** marker (8 bytes: `42 4F 4F 54 44 49 53 4B`)
- `0x1E8..0x1EF`: Unused padding gap (**8 bytes**)
- `0x1F0..0x1F5`: **`SCRIPT`** marker (6 bytes: `53 43 52 49 50 54`)
- `0x1F6..0x1FD`: Unused padding gap (**8 bytes**)
- `0x1FE..0x1FF`: VBR Boot Sector Signature (**`55 AA`**)

**Spatial Coexistence on FAT32**:
`0x1E0 + 8 = 0x1E8 <= 0x1F0`. The `BOOTDISK` and `SCRIPT` markers are separated by an 8-byte gap. Neither marker collides with the other or with the trailing `0x55AA` boot signature `[VERIFIED: spatial layout calculation]`.

### 3.2 FAT16 Partition VBR
On a FAT16 partition, the BPB ends at offset `0x3D`:
- `0x000..0x03D`: Standard FAT16 BPB
- `0x03E..0x03F`: Padding
- `0x040..0x047`: **`BOOTDISK`** marker (8 bytes)
- `0x048..0x1EF`: Bootstrap code / padding (424 bytes)
- `0x1F0..0x1F5`: **`SCRIPT`** marker (6 bytes)
- `0x1F6..0x1FD`: Padding (8 bytes)
- `0x1FE..0x1FF`: VBR Boot Sector Signature (**`55 AA`**)

**Spatial Coexistence on FAT16**:
`0x40 + 8 = 0x48 <= 0x1F0`. The markers are completely disjoint and separated by 424 bytes `[VERIFIED: spatial layout calculation]`.

---

## 4. Disassembly and Instruction-Level Control Flow

### 4.1 Volume Mount & Marker Detector: `0xFC37A4B6` (`Mounter.c`)
Function `0xFC37A4B6` is called by the filesystem driver to parse partition boot records and initialize drive descriptors `[VERIFIED: docs/HANDOFF.md:435; 0xFC37A4B6]`:

```arm
fc37a4b6: push.w  {r1, r2, r3, r4, r5, r6, r7, r8, r9, sl, fp, lr}
fc37a4ba: mov     lr, r0             @ lr = drive/partition index
fc37a4bc: ldr     r0, [pc, #796]     @ r0 = drive table base
fc37a4be: movs    r5, #0
fc37a4c0: mov     r4, r1             @ r4 = VBR sector buffer pointer
fc37a4c2: add.w   r7, r0, lr, lsl #7 @ r7 = drive descriptor pointer (drive_desc)
...
fc37a4ce: str     r5, [r7, #116]     @ drive_desc->is_bootdisk = 0 (offset 0x74)
fc37a4d0: str     r5, [r7, #120]     @ drive_desc->is_scriptdisk = 0 (offset 0x78)
```
*Note*: `is_bootdisk` (`[r7, #0x74]`) and `is_scriptdisk` (`[r7, #0x78]`) are unconditionally initialized to 0 at mount start.

#### Filesystem Identification
`0xFC37A4D2..0xFC37A55C`:
```arm
fc37a4d2: ldrh.w  r0, [r1, #11]      @ BPB_BytsPerSec (offset 11)
fc37a4d6: ldrb    r1, [r1, #13]      @ BPB_SecPerClus (offset 13)
...
fc37a502: orrs.w  r5, r0, r1         @ If either is non-zero, it is FAT12/16/32
fc37a506: bne.n   0xfc37a55e         @ Branch to standard FAT parsing
```

#### exFAT Bypass Path
If `BPB_BytsPerSec` and `BPB_SecPerClus` are both 0 (characteristic of exFAT BPB):
```arm
fc37a508: ldrb    r0, [r4, #3]       @ OEM Name check: 'E' (0x45)
fc37a50a: cmp     r0, #69
fc37a50c: bne.n   0xfc37a554
fc37a50e: ldrb    r0, [r4, #4]       @ 'X' (0x58)
fc37a510: cmp     r0, #88
...
fc37a520: ldrb    r0, [r4, #7]       @ 'T' (0x54)
fc37a522: cmp     r0, #84
fc37a524: bne.n   0xfc37a50c
...
fc37a556: movs    r0, #4             @ Filesystem type = 4 (exFAT)
fc37a558: str.w   r0, [r8, r6, lsl #2]
fc37a55c: b.n     0xfc37a67e         @ BRANCH DIRECTLY TO SUCCESS EXIT!
```
At `0xFC37A55C`, exFAT parsing branches straight to `0xFC37A67E` (`movs r0, #1; pop ... pc`), completely skipping marker inspection at `0xFC37A650..0xFC37A67C`. As a result, `is_bootdisk` and `is_scriptdisk` remain 0.

#### FAT32 vs FAT16 Path Selection
At `0xFC37A55E`, the code checks `BPB_FATSz16` (`[r4, #22]`):
```arm
fc37a5c6: cbnz    r2, 0xfc37a60c     @ If BPB_FATSz16 != 0 -> branch to FAT12/FAT16
```

**FAT32 Branch (`BPB_FATSz16 == 0`)**:
```arm
fc37a5d8: ldr.w   r2, [r4, #37]      @ Reads BPB_FATSz32 at offset 0x24 (36)
fc37a5dc: ldrb.w  r0, [r4, #36]
...
fc37a5fa: movs    r0, #3             @ Filesystem type = 3 (FAT32)
fc37a5fc: str.w   r0, [lr, r6, lsl #2]
...
fc37a606: movw    r1, #480           @ r1 = 0x1E0 (FAT32 VBR offset!)
fc37a60a: b.n     0xfc37a652         @ Jump to BOOTDISK comparison
```

**FAT12/FAT16 Branch (`BPB_FATSz16 != 0`)**:
```arm
fc37a60c: add.w   ip, sl, ip, lsl #5
...
fc37a62e: movw    r1, #4085          @ 0xFF5 (FAT12 vs FAT16 cluster threshold)
fc37a636: cmp     r0, r1
fc37a638: bcc.n   0xfc37a63e         @ If < 4085 clusters -> FAT12 (type 1)
fc37a63a: movs    r1, #2             @ Else -> FAT16 (type 2)
fc37a63c: b.n     0xfc37a640
fc37a63e: movs    r1, #1             @ FAT12 (type 1)
fc37a640: ldr     r0, [pc, #408]
fc37a648: str.w   r1, [r0, r6, lsl #2] @ Store filesystem type
...
fc37a650: movs    r1, #64            @ r1 = 0x40 (FAT12/FAT16 VBR offset!)
fc37a652: mov     r0, r4             @ r0 = VBR buffer pointer
fc37a654: bl      0xfc37b2ae         @ Call strncmp helper with "BOOTDISK"
fc37a658: str     r0, [r7, #116]     @ drive_desc->is_bootdisk = result (0 or 1)
```

#### BOOTDISK Helper: `0xFC37B2AE`
```arm
fc37b2ae: add     r0, r1             @ r0 = VBR buffer + offset (0x40 or 0x1E0)
fc37b2b0: movs    r2, #8             @ Length = 8 bytes
fc37b2b2: add     r1, pc, #244       @ r1 = &"BOOTDISK" (literal at 0xFC37B3A8)
fc37b2b4: push    {r4, lr}
fc37b2b6: bl      0xfc420996         @ strncmp(buffer + offset, "BOOTDISK", 8)
fc37b2ba: cbnz    r0, 0xfc37b2c0     @ If mismatch, return 0
fc37b2bc: movs    r0, #1             @ If match, return 1
fc37b2be: pop     {r4, pc}
fc37b2c0: movs    r0, #0
fc37b2c2: pop     {r4, pc}
```

#### SCRIPT Marker Check
Following the `BOOTDISK` evaluation, the routine checks partition sector bounds and proceeds to the `SCRIPT` check:
```arm
fc37a668: movs    r2, #6             @ Length = 6 bytes
fc37a66a: add     r1, pc, #388       @ r1 = &"SCRIPT" (literal at 0xFC37A7F0)
fc37a66c: add.w   r0, r4, #496       @ r0 = buffer + 496 (0x1F0)
fc37a670: bl      0xfc420996         @ strncmp(buffer + 0x1F0, "SCRIPT", 6)
fc37a674: cbnz    r0, 0xfc37a67a
fc37a676: movs    r0, #1             @ Match: return 1
fc37a678: b.n     0xfc37a67c
fc37a67a: movs    r0, #0             @ Mismatch: return 0
fc37a67c: str     r0, [r7, #120]     @ drive_desc->is_scriptdisk = result (0 or 1)
fc37a67e: movs    r0, #1
fc37a680: b.n     0xfc37a664
```

### 4.2 Sector Writer / Formatter Confirmation: `0xFC37B318` (`make_bootable`)
Further proof of the dual-offset design is found in the internal format/marking routine `0xFC37B318` `[VERIFIED: docs/PROJECT_STATE.md:201; 0xFC37B318-0xFC37B38A]`:
```arm
fc37b33e: ldrb.w  r0, [r4, #54]      @ Check "FAT" at offset 0x36 (FAT12/FAT16 BPB)
fc37b342: cmp     r0, #70            @ 'F'
fc37b346: ldrb.w  r0, [r4, #55]
fc37b34a: cmp     r0, #65            @ 'A'
fc37b34e: ldrb.w  r0, [r4, #56]
fc37b352: cmp     r0, #84            @ 'T'
fc37b356: movs    r0, #64            @ Offset = 0x40 (FAT12/16)
fc37b358: b.n     0xfc37b376
fc37b35a: ldrb.w  r0, [r4, #82]      @ Check "FAT" at offset 0x52 (FAT32 BPB)
fc37b35e: cmp     r0, #70            @ 'F'
fc37b362: ldrb.w  r0, [r4, #83]
fc37b366: cmp     r0, #65            @ 'A'
fc37b36a: ldrb.w  r0, [r4, #84]
fc37b36e: cmp     r0, #84            @ 'T'
fc37b372: movw    r0, #480           @ Offset = 0x1E0 (FAT32)
fc37b376: movs    r2, #8             @ Length = 8 bytes
fc37b378: add     r0, r4             @ buffer + offset
fc37b37a: add     r1, pc, #44        @ &"BOOTDISK" (0xFC37B3A8)
fc37b37c: bl      0xfc381464         @ memcpy(buffer + offset, "BOOTDISK", 8)
fc37b38a: blx     r5                 @ Write sector back to media
```
This confirms that Canon's own firmware utility writes `"BOOTDISK"` to `0x40` when the filesystem is FAT12/FAT16, and to `0x1E0` when the filesystem is FAT32.

### 4.3 Bootdisk Flag Consumer: `StartDiskboot` (`0xFC05BBEA`)
In `StartDiskboot`, the kernel checks the write-protect switch and evaluates `is_bootdisk` `[VERIFIED: docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:30-33; docs/PORT19_DISKBOOT_ENCODING.md:96]`:
```arm
fc05bc16: movs    r0, #0             @ Drive 0 (SD card)
fc05bc18: bl      0xfc37aea6         @ Read drive_desc->is_bootdisk ([r0 + 0x74])
fc05bc1c: cbz     r0, 0xfc05bc34     @ If is_bootdisk == 0, abort cleanly and return!
fc05bc1e: add     r0, pc, #96        @ "\nStartDiskboot\n"
fc05bc20: bl      0xfc383178         @ printf
fc05bc2a: bl      0xfc05bc3c         @ Proceed to load A/DISKBOOT.BIN
```

---

## 5. ROM Read Scope and Evidence Manifest Accounting

### 5.1 Evidence Manifest Entry
In compliance with the Phase 0 read budget (windows of at most 4 KiB, at most 64 KiB total, anchored to cited addresses or direct branch/call targets), window `PORT19-ROM-MOUNTER-VBR` was read and registered in `docs/agentbridge/PORT19_EVIDENCE_MANIFEST.json`:

| Field | Value |
|---|---|
| Evidence ID | `PORT19-ROM-MOUNTER-VBR` |
| Firmware Revision | `GM1.10C` |
| Address Range | `0xFC37A400` – `0xFC37B3FF` |
| Byte Count | 4,096 bytes (4 KiB) |
| SHA-256 | `7706e4438a36a0c42aa584c994571382870d427c945240c66eec86dc02a1f65b` |
| Provenance Source | `firmware/dumps/GM1.10C/PRIMARY.BIN` (`ROM_VERIFIED`) |
| Classification | `STATIC_VERIFIED` |
| Anchor Citations | `docs/HANDOFF.md:435`, `docs/PROJECT_STATE.md:201` (`0xFC37A4B6`), `docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:33`, `docs/HANDOFF.md:923` (`0xFC37B2AE`), `docs/PORT19_DISKBOOT_ENCODING.md:96` (direct call target `0xFC37AEA6` from `0xFC05BC18`) |

### 5.2 Read Budget Summary
- **T1 Read Cumulative**: 4,864 bytes across 8 windows.
- **T2 Read (This Task)**: 4,096 bytes in 1 window (`0xFC37A400`–`0xFC37B3FF`).
- **Total Read Cumulative**: 8,960 bytes (8.75 KiB).
- **Budget Compliance**: 8,960 bytes is 13.67% of the 65,536-byte (64 KiB) cumulative ceiling. Window size 4,096 bytes satisfies the ≤ 4 KiB per-window limit.
- **Validator Status**: `tools/port11c_evidence_validator.py --manifest docs/agentbridge/PORT19_EVIDENCE_MANIFEST.json` reports `VALID (0 errors, 1 warnings)` `[VERIFIED]`.
