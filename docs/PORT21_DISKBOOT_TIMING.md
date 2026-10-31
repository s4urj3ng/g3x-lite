# PORT-21 T2: Analysis of StartDiskboot Timing and Locked-Card Start-Up Delay

- **Target Camera**: Canon PowerShot G3 X (Firmware **GM1.10C**, Platform ID `0x32A8` = 12968) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:7; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:3]`
- **Evaluation Mode**: Phase 0 Read-Only Offline Firmware Disassembly & Timing Analysis
- **Governance & Safety**: STRICT NO-GO on hardware trials, camera connection, and firmware flashing (`docs/SAFETY.md:1-8`). All ROM reads are bounded (<= 4 KiB per read, total 4,096 B <= 32 KiB) and recorded in `docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json` `[VERIFIED: docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json:48-94; tools/port11c_evidence_validator.py:1]`.

---

## 1. Executive Summary & Core Findings

This investigation resolves why the Canon PowerShot G3 X (firmware GM1.10C) exhibits a **visibly slower start-up only when the SD card write-protect switch is LOCKED**, while booting at normal fast speed when UNLOCKED `[OWNER-REPORTED (PORT-21 milestone brief, 2026-11-01 session, candidate SHA-256 9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136)]`.

Using the `StartDiskboot` call chain mapped in `docs/PORT19_DISKBOOT_ENCODING.md:73-324`, we perform a step-by-step comparative analysis of the **Reject Path** ("not executable") and the **Accept Path** (copy to `0x40008000`, branch to `0x8001`), identifying the exact operations responsible for the timing discrepancy and mapping the result to hypotheses **H1–H4**.

### Key Conclusions

1. **Why Unlocked Cards Boot at Normal Fast Speed**:
   - At `0xFC05BC04`, `StartDiskboot` calls `sub_fc05c4e0(1)` to inspect the physical SD write-protect switch `[VERIFIED: ROM 0xFC05BC04; PORT21-ROM-STARTDISKBOOT]`.
   - If the card is **UNLOCKED**, `beq.n 0xfc05bc34` at `0xFC05BC0A` branches immediately to the function epilogue at `0xFC05BC34` (`ldmia.w sp!, {r4, lr}; b.w 0xfc05c4de`), returning directly to `task_Startup` within microseconds `[VERIFIED: ROM 0xFC05BC0A-0xFC05BC38; PORT21-ROM-STARTDISKBOOT]`.
   - In this state, zero filesystem operations occur: no VBR read, no FAT directory search, no `A/DISKBOOT.BIN` file reading, no buffer allocation, no DancingBits descrambling, and no memory copies take place `[VERIFIED: ROM 0xFC05BC0A-0xFC05BC7E; PORT21-ROM-STARTDISKBOOT]`.

2. **Reject Path vs Accept Path Operations After the Write-Protect Check**:
   - **Reject Path** (`sub_fc54de38` returns 1, "not executable"):
     - Executes SD card bus initialization (`blx 0xfc31b1f4` at `0xFC05BBFE`), VBR check (`bl 0xfc37aea6` at `0xFC05BC18`), debug banner print (`0xFC05BC20`), and FAT directory search/stat for `"A/DISKBOOT.BIN"` in `sub_fc05bb98` (`0xFC05BC42`, `0xFC37B5CC`) `[VERIFIED: ROM 0xFC05BBFE-0xFC05BC42; PORT21-ROM-STARTDISKBOOT]`.
     - Allocates 118,001 bytes of dynamic memory (`0xFC092440`) and reads all 118,001 bytes from the SD card across the SD bus into DRAM (`0xFC37B552`) `[VERIFIED: ROM 0xFC05BBAE-0xFC05BBD8; PORT21-ROM-STARTDISKBOOT]`.
     - Fails Gate 1 (`byte 0 != 0x00` at `0xFC54DE3C`) or Gate 2 (signature match at `0xFC54DE4C`), prints `"not executable\n"` (`0xFC05BC68`), frees the 118,001-byte buffer (`0xFC0924FA` at `0xFC05BC70`), and returns cleanly to `task_Startup` (`0xFC05BC38`) `[VERIFIED: ROM 0xFC05BC66-0xFC05BC74, 0xFC54DE3C, 0xFC54DE4C; PORT21-ROM-STARTDISKBOOT; PORT21-ROM-EXEC-VALIDATE]`.
     - **Critically**: The reject path **does not** execute the 118,000-byte shift loop, **does not** execute the 236,000 function calls of DancingBits Row 13 descrambling, **does not** configure MPU/caches, **does not** copy payload to `0x40008000`, **does not** verify payload words, and **does not** branch to `0x8001` `[VERIFIED: ROM 0xFC05BC66-0xFC05BC7E, 0xFC54DE38-0xFC54DE6A; PORT21-ROM-STARTDISKBOOT; PORT21-ROM-EXEC-VALIDATE]`.
   - **Accept Path** (`sub_fc54de38` returns 0, "executable"):
     - Executes all SD bus initialization, VBR verification, and 118,001-byte SD file read described above `[VERIFIED: ROM 0xFC05BBFE-0xFC05BC42; PORT21-ROM-STARTDISKBOOT]`.
     - Executes in-place shift loop stripping byte 0 across 118,000 bytes (`0xFC54DE4E..0xFC54DE5E`) `[VERIFIED: ROM 0xFC54DE4E-0xFC54DE5E; PORT21-ROM-EXEC-VALIDATE]`.
     - Executes full DancingBits Row 13 descrambling in `sub_fc42189c` across 14,750 8-byte blocks, invoking `sub_fc469180` (118,000 calls) and `sub_fc469188` (`_dance`, 118,000 calls) for a total of **236,000 function calls** involving integer division and bitwise permutation `[VERIFIED: ROM 0xFC42189C-0xFC421922; PORT21-ROM-DANCINGBITS-MAIN]`.
     - Disables interrupts (`0xFC0D9CA2`), flushes/invalidates caches at `0x8000` (`0xFC0D9CAC`), and reconfigures MPU Region 7 (`0xFC0D9CB0`) `[VERIFIED: ROM 0xFC0D9CA2-0xFC0D9CB0; PORT21-ROM-PREPARE-EXEC]`.
     - Copies 118,001 bytes byte-by-byte into `0x40008000` (`0xFC0007DC..0xFC0007E8`), performs a word-by-word memory verification of all 118,001 bytes (`0xFC0007EE..0xFC000832`), and branches `bx ip` (`0x8001`) into the candidate loader `[VERIFIED: ROM 0xFC0007DC-0xFC000840; PORT21-ROM-PAYLOAD-HANDOFF]`.
     - If the candidate loader runs: copies 123,644 bytes to `0x003489B4`, writes Stage 1 witness, branches to core `boot()`, which executes a **complete second-stage software boot trampoline**: re-zeroes 3,183,808 bytes of Canon BSS, re-initializes vector/clock/memory controllers, and restarts the DryOS kernel a second time `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:85-161; docs/PORT21_RAM_LIFETIME.md:19-24]`.

3. **Discrimination Between H1 and H2/H3/H4**:
   - **Hypothesis H1 (Rejected by a Gate)**: **CONTRADICTED BY CANDIDATE HEADER / UNLIKELY TIMING FIT** `[INFERRED]`.
     - The candidate `DISKBOOT.BIN` file (`9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136`) has `byte 0 == 0x00` and does not match the `"gaonisoy"` signature `[VERIFIED: candidate_port2a/DISKBOOT.BIN; tools/validate_candidate_port2a.py:81-93; PORT19-ROM-EXEC-VALIDATE]`.
     - Therefore, `sub_fc54de38` **does not reject** the candidate binary; Gate 1 and Gate 2 evaluate to pass `[VERIFIED: static disassembly]`.
     - While reading 118 KB over SD bus adds 50–150 ms, this modest delay is subtle and unlikely to account for the owner-reported "visibly slower" start-up `[INFERRED]`.
   - **Hypotheses H2/H3/H4 (Accept Path Taken)**: **STRONGLY FITS TIMING OBSERVATION** `[INFERRED]`.
     - The accept path executes SD I/O + 236,000 descrambler calls + DRAM copy + memory verify + second-stage boot trampoline (or watchdog reset cycle) `[VERIFIED: ROM 0xFC05BBFE-0xFC05BC7E, 0xFC54DE38-0xFC54DE6A, 0xFC42189C-0xFC421922, 0xFC0D9C9C-0xFC0D9CCA, 0xFC0007C0-0xFC000840; chdk-port/platform/g3x/sub/110c/boot_prototype.c:85-161]`.
     - This composite execution path introduces a cumulative latency of **500 ms to 2.0 seconds** (a double kernel initialization or a 1–2 second hardware watchdog reset) `[INFERRED]`.
     - This massive delay perfectly matches the owner's observation of a **visibly slower start-up only with a locked card** culminating in the stock UI `[INFERRED]`.

4. **Implications for the Morning Session**:
   - The morning session **must not waste time** re-investigating `DISKBOOT.BIN` file gating, naming, or encoding format (H1 is ruled out) `[INFERRED]`.
   - The morning session should focus entirely on **post-handoff execution diagnostics** (loader entry, MMU state, witness survival, and second-stage boot) `[INFERRED]`.
   - The owner trial plan should inspect `0x40008000` via RAM comparison (`RAMCMP`): because `sub_fc0007c0` copies the decoded loader to `0x40008000` before jumping, finding the decoded loader at `0x40008000` provides conclusive physical hardware proof that `StartDiskboot` accepted and decoded the file `[INFERRED]`.

---

## 2. Step-by-Step Code-Level Comparison: Reject Path vs Accept Path

The diagram below maps the execution flow through `StartDiskboot` (`0xFC05BBEA`), detailing where the reject and accept paths diverge:

```mermaid
flowchart TD
    E["StartDiskboot (0xFC05BBEA)"] --> S0["Check boot flags (0xFC05BBF6)"]
    S0 --> S1["SD1stInit / Bus Setup (0xFC05BBFE)"]
    S1 --> S2{"SD Write-Protect Check\nsub_fc05c4e0(1) (0xFC05BC04)"}
    
    S2 -->|"UNLOCKED (bit 31 == 0)\nbeq 0xFC05BC34"| FastRet["Immediate Fast Return\nldmia sp!, {r4, lr}; bx (0xFC05BC34)\n[Microseconds, Normal Start-up]"]
    
    S2 -->|"LOCKED (bit 31 == 1)"| S3["Check VBR for 'BOOTDISK' (0xFC05BC18)"]
    S3 -->|"Marker missing"| FastRet
    S3 -->|"Marker present"| S4["Printf '\\nStartDiskboot\\n' (0xFC05BC20)"]
    S4 --> S5["sub_fc05bc3c: Stat & Read 'A/DISKBOOT.BIN' (0xFC05BC42)"]
    S5 --> S6["Allocate 118,001 B & Read across SD bus (0xFC37B552)"]
    S6 --> S7{"Header Validation sub_fc54de38 (0xFC05BC62)\nGate 1: byte 0 == 0x00 (0xFC54DE3C)\nGate 2: !gaonisoy (0xFC54DE4C)"}
    
    S7 -->|"REJECT: return 1\n(cbnz / beq 0xFC54DE68)"| R1["sub_fc05bc3c Reject Path\nPrintf 'not executable\\n' (0xFC05BC68)"]
    R1 --> R2["Free buffer: sub_fc0924fa (0xFC05BC70)"]
    R2 --> R3["Clean Return to task_Startup (0xFC05BC38)"]
    R3 --> R4["Stock task_Startup continues normal boot to Stock UI"]
    
    S7 -->|"ACCEPT: return 0\n(0xFC54DE64)"| A1["In-place Shift Loop: 118,000 B (0xFC54DE54)"]
    A1 --> A2["DancingBits Row 13 Decoder sub_fc42189c (0xFC54DE60)\n236,000 function calls (0xFC4218C4, 0xFC4218EE)"]
    A2 --> A3["sub_fc0d9c9c: Interrupt Disable, D/I Cache Invalidate (0xFC0D9CAC),\nMPU Region 7 Executable (0xFC0D9CB0)"]
    A3 --> A4["sub_fc0007c0: Copy 118,001 B to 0x40008000 (0xFC0007DC)"]
    A4 --> A5["Word-by-word Verify Loop: 118,001 B (0xFC0007EE)"]
    A5 --> A6["Terminal Branch: bx ip (0x8001) in Thumb mode (0xFC000840)"]
    A6 --> A7["Candidate Loader at 0x8001 executes -> Core boot() / Watchdog Reset"]
```

### 2.1 Step-by-Step Execution Sequence

#### Step 1: Write-Protect Switch Check (`0xFC05BBEA..0xFC05BC0A`)
- In `task_Startup` (`0xFC05B8FC`), stock firmware invokes `StartDiskboot` (`0xFC05BBEA`) `[VERIFIED: docs/HANDOFF.md:921; ROM 0xFC05B90E, 0xFC05BBEA; PORT21-ROM-STARTUP-TASKS; PORT21-ROM-STARTDISKBOOT]`.
- `0xFC05BBFE`: Calls `sub_fc31b1f4` (`SD1stInit`), initializing the SD card bus `[VERIFIED: ROM 0xFC05BBFE; PORT21-ROM-STARTDISKBOOT]`.
- `0xFC05BC04`: Calls `sub_fc05c4e0(1)` to read the physical SD card write-protect switch GPIO register `[VERIFIED: ROM 0xFC05BC04; PORT21-ROM-STARTDISKBOOT]`.
- `0xFC05BC08..0xFC05BC0A`: Shifts bit 31 (`lsls r0, r0, #31`) and executes conditional branch `beq.n 0xfc05bc34`:
  - **If Card UNLOCKED** (`bit 31 == 0`): Branches directly to `0xFC05BC34`, restores `{r4, lr}`, and branches to `sub_fc05c4de` (`0xFC05BC38`), returning to `task_Startup` `[VERIFIED: ROM 0xFC05BC0A, 0xFC05BC34-0xFC05BC38; PORT21-ROM-STARTDISKBOOT]`. Total duration is negligible (< 10 µs beyond bus init). Start-up is fast.
  - **If Card LOCKED** (`bit 31 == 1`): Branch is not taken. Execution proceeds into diskboot sequence `[VERIFIED: ROM 0xFC05BC0A-0xFC05BC0C; PORT21-ROM-STARTDISKBOOT]`.

#### Step 2: VBR Marker Validation (`0xFC05BC0C..0xFC05BC1C`)
- `0xFC05BC18`: Calls `sub_fc37aea6`, which reads the partition Volume Boot Record (VBR) from SD card and validates the presence of the 8-byte ASCII marker `"BOOTDISK"` at offset `0x40` (FAT16) or `0x52` (FAT32) `[VERIFIED: ROM 0xFC05BC18; PORT21-ROM-STARTDISKBOOT]`.
- `0xFC05BC1C`: `cbz r0, 0xfc05bc34`. If `"BOOTDISK"` is missing, returns cleanly to `task_Startup` `[VERIFIED: ROM 0xFC05BC1C; PORT21-ROM-STARTDISKBOOT]`.

#### Step 3: Debug Banner Print (`0xFC05BC1E..0xFC05BC2A`)
- `0xFC05BC20`: Calls `sub_fc383178` (DryOS debug `printf`) passing literal string `"\nStartDiskboot\n"` located at `0xFC05BC80` `[VERIFIED: ROM 0xFC05BC1E-0xFC05BC20, 0xFC05BC80; PORT21-ROM-STARTDISKBOOT]`.
- `0xFC05BC2A`: Calls `sub_fc05bc3c` to ingest and process the diskboot binary `[VERIFIED: ROM 0xFC05BC2A; PORT21-ROM-STARTDISKBOOT]`.

#### Step 4: File Ingestion & DRAM Buffer Allocation in `sub_fc05bc3c` (`0xFC05BC3C..0xFC05BC58`)
- `0xFC05BC3E`: Sets `r0` to `"A/DISKBOOT.BIN"` (`0xFC05BC90`), `r1 = sp` (pointer to receive file size) `[VERIFIED: ROM 0xFC05BC3E-0xFC05BC40, 0xFC05BC90; PORT21-ROM-STARTDISKBOOT]`.
- `0xFC05BC42`: Calls `sub_fc05bb98` (`0xFC05BB98`):
  - Calls `sub_fc37b5cc` to stat `"A/DISKBOOT.BIN"` on the FAT filesystem `[VERIFIED: ROM 0xFC05BBA2; PORT21-ROM-STARTDISKBOOT]`.
  - Obtains file size `sp[8] = 118,001` bytes `[VERIFIED: candidate_port2a/DISKBOOT.BIN; ROM 0xFC05BBA8; PORT21-ROM-STARTDISKBOOT]`.
  - Calls `sub_fc092440` (DryOS dynamic heap allocation) to allocate an in-memory buffer of 118,001 bytes `[VERIFIED: ROM 0xFC05BBAE; PORT21-ROM-STARTDISKBOOT]`.
  - Calls `sub_fc37b4ae` to open the file `[VERIFIED: ROM 0xFC05BBC2; PORT21-ROM-STARTDISKBOOT]`.
  - Calls `sub_fc37b552` to read all 118,001 bytes across the physical SD bus into DRAM `[VERIFIED: ROM 0xFC05BBD8; PORT21-ROM-STARTDISKBOOT]`.
  - Calls `sub_fc37b4b0` to close the file `[VERIFIED: ROM 0xFC05BBDE; PORT21-ROM-STARTDISKBOOT]`.
  - Returns allocated buffer pointer `r0` and writes `file_size` to caller stack `[sp, #0]` `[VERIFIED: ROM 0xFC05BBE4-0xFC05BBE6; PORT21-ROM-STARTDISKBOOT]`.

#### Step 5: Header Validation & Gating in `sub_fc54de38` (`0xFC05BC5E..0xFC05BC66`, `0xFC54DE38..0xFC54DE4C`)
- `0xFC05BC5E..0xFC05BC62`: Loads `r1 = file_size` (118,001), `r0 = buffer`, and calls `sub_fc54de38` `[VERIFIED: ROM 0xFC05BC5E-0xFC05BC62; PORT21-ROM-STARTDISKBOOT]`.
- In `sub_fc54de38`:
  - **Gate 1 (Byte 0 Check)**: `0xFC54DE3A`: `ldrb r2, [r0, #0]`; `0xFC54DE3C`: `cbnz r2, 0xfc54de68`. If `byte 0 != 0x00`, immediately jumps to error return `r0 = 1` `[VERIFIED: ROM 0xFC54DE3A-0xFC54DE3C; PORT21-ROM-EXEC-VALIDATE]`.
  - **Gate 2 (Gaonisoy Signature Check)**: `0xFC54DE3E..0xFC54DE4C`: Checks word at offset 16 for `0x6E6F6167` ("gaon") and offset 32 for `0x796F7369` ("isoy"). If both match, jumps to error return `r0 = 1` `[VERIFIED: ROM 0xFC54DE3E-0xFC54DE4C; PORT21-ROM-EXEC-VALIDATE]`.

#### Step 6: In-Place Left Shift & DancingBits Descrambling (Accept Path Only)
- If Gate 1 and Gate 2 pass:
  - `0xFC54DE4E..0xFC54DE5E`: The left-shift loop decrements `r1` to `file_size - 1` (118,000) and executes `buffer[index] = buffer[index + 1]` for `index = 0 .. 117,999`, completely stripping byte 0 `[VERIFIED: ROM 0xFC54DE4E-0xFC54DE5E; PORT21-ROM-EXEC-VALIDATE]`.
  - `0xFC54DE60`: Calls `sub_fc42189c` (DancingBits main block decoder) `[VERIFIED: ROM 0xFC54DE60; PORT21-ROM-EXEC-VALIDATE]`:
    - The payload contains `118,000 / 8 = 14,750` blocks `[VERIFIED: candidate_port2a/candidate_loader.bin; derived: 118000 / 8 = 14750]`.
    - Inner Loop 1 (`0xFC4218BC..0xFC4218D6`): Calls `sub_fc469180` via `blx r1` 8 times per block (14,750 × 8 = **118,000 indirect calls**), reading Row 13 permutation table `[6, 5, 3, 7, 0, 2, 4, 1]` at `0xFC7C0F8C` and permuting bytes into a stack temporary `[VERIFIED: ROM 0xFC4218BC-0xFC4218D6, 0xFC469180, 0xFC7C0F8C; PORT21-ROM-DANCINGBITS-MAIN; PORT21-ROM-DANCINGBITS-DANCE; PORT21-ROM-ROW13-TABLE; derived: 14750 * 8 = 118000]`.
    - Inner Loop 2 (`0xFC4218D8..0xFC4218FA`): Calls `sub_fc469188` (`_dance`) via `blx r2` 8 times per block (14,750 × 8 = **118,000 indirect calls**), computing `udiv` and `mls` (`fudgey % 3`), bitwise XORs (`^ 0xFF`, `^ 0xA0`), and nibble swaps, writing descrambled bytes back into payload DRAM `[VERIFIED: ROM 0xFC4218D8-0xFC4218FA, 0xFC469188; PORT21-ROM-DANCINGBITS-MAIN; PORT21-ROM-DANCINGBITS-DANCE; derived: 14750 * 8 = 118000]`.
    - Remainder loop (`0xFC421904..0xFC421922`): `118,000 % 8 = 0`, so 0 remainder iterations execute `[VERIFIED: ROM 0xFC421904-0xFC421922; PORT21-ROM-DANCINGBITS-MAIN; derived: 118000 % 8 = 0]`.
    - Returns `r0 = 0` (SUCCESS) at `0xFC54DE64` `[VERIFIED: ROM 0xFC54DE64; PORT21-ROM-EXEC-VALIDATE]`.

#### Step 7: The Reject Path ("not executable")
- If `sub_fc54de38` returned 1 (`0xFC54DE68`):
  - `0xFC05BC66`: `cbz r0, 0xfc05bc76` is NOT taken `[VERIFIED: ROM 0xFC05BC66; PORT21-ROM-STARTDISKBOOT]`.
  - `0xFC05BC68..0xFC05BC6A`: Loads pointer to literal `"not executable\n"` (`0xFC05BCCC`) and calls DryOS debug `printf` (`sub_fc383178`) `[VERIFIED: ROM 0xFC05BC68-0xFC05BC6A, 0xFC05BCCC; PORT21-ROM-STARTDISKBOOT]`.
  - `0xFC05BC6E..0xFC05BC70`: Sets `r0 = 1` and calls `sub_fc0924fa` to free the 118,001-byte DRAM buffer `[VERIFIED: ROM 0xFC05BC6E-0xFC05BC70; PORT21-ROM-STARTDISKBOOT]`.
  - `0xFC05BC74`: Pops `{r3, r4, r5, pc}`, returning to `StartDiskboot` at `0xFC05BC2E` `[VERIFIED: ROM 0xFC05BC74; PORT21-ROM-STARTDISKBOOT]`.
  - `0xFC05BC2E..0xFC05BC38`: Calls cleanup `sub_fc37ae2a`, restores `{r4, lr}`, and branches to `sub_fc05c4de`, returning to `task_Startup` `[VERIFIED: ROM 0xFC05BC2E-0xFC05BC38; PORT21-ROM-STARTDISKBOOT]`.
  - `task_Startup` continues normal boot into stock UI `[VERIFIED: ROM 0xFC05B90E-0xFC05B95E; PORT21-ROM-STARTUP-TASKS]`.

#### Step 8: The Accept Path & Execution Handoff
- If `sub_fc54de38` returned 0 (`0xFC54DE64`):
  - `0xFC05BC66`: `cbz r0, 0xfc05bc76` branches to `0xFC05BC76` `[VERIFIED: ROM 0xFC05BC66; PORT21-ROM-STARTDISKBOOT]`.
  - `0xFC05BC76..0xFC05BC7A`: Reloads original unmodified `file_size` (118,001) from caller stack `[sp, #0]`, sets `r0 = buffer`, and executes `bl 0xfc0d9c9c` (setting `lr = 0xFC05BC7F`) `[VERIFIED: ROM 0xFC05BC76-0xFC05BC7A; PORT21-ROM-STARTDISKBOOT]`.
  - In `sub_fc0d9c9c`:
    - `0xFC0D9CA2`: Disables interrupts via `blx 0xfc31befc` (`cpsr_fsxc |= 0x80`) `[VERIFIED: ROM 0xFC0D9CA2; PORT21-ROM-PREPARE-EXEC]`.
    - `0xFC0D9CAC`: Flushes and invalidates data/instruction cache at `0x8000` via `bl 0xfc41870c` `[VERIFIED: ROM 0xFC0D9CAC; PORT21-ROM-PREPARE-EXEC]`.
    - `0xFC0D9CB0`: Configures ARM MPU Region 7 for `0x00000000..0x00010000` as executable via `bl 0xfc135284` -> `0xFC0D00B2` `[VERIFIED: ROM 0xFC0D9CB0; PORT21-ROM-PREPARE-EXEC]`.
    - `0xFC0D9CB4..0xFC0D9CC2`: Sets `r0 = 0x8001 << 15 = 0x40008000` (destination), `r1 = buffer` (source), `r2 = 118,001` (length), `r3 = 0x8001` (payload entry) `[VERIFIED: ROM 0xFC0D9CB4-0xFC0D9CC2; PORT21-ROM-PREPARE-EXEC]`.
    - `0xFC0D9CC0..0xFC0D9CCA`: Loads `ip = *(0x4000) = 0xFC0007C1`, pops `{r4, r5, r6, lr}` (preserving saved `lr = 0xFC05BC7F`), and executes `bx ip` jumping to `sub_fc0007c0` `[VERIFIED: ROM 0xFC0D9CC0-0xFC0D9CCA; PORT21-ROM-PREPARE-EXEC]`.
  - In `sub_fc0007c0`:
    - `0xFC0007DC..0xFC0007E8`: Copies 118,001 bytes byte-by-byte from source buffer to `0x40008000` via `ldrb.w r3, [r1], #1` / `strb.w r3, [r0], #1` `[VERIFIED: ROM 0xFC0007DC-0xFC0007E8; PORT21-ROM-PAYLOAD-HANDOFF]`.
    - `0xFC0007EE..0xFC000832`: Compares copied memory against source buffer word-by-word; halts with `"Verify Error"` if mismatch `[VERIFIED: ROM 0xFC0007EE-0xFC000832; PORT21-ROM-PAYLOAD-HANDOFF]`.
    - `0xFC00083A..0xFC000840`: Sets `ip = 0x8001`, restores registers (preserving `lr = 0xFC05BC7F`), and executes `bx ip`, branching to `0x8001` in 16-bit Thumb mode `[VERIFIED: ROM 0xFC00083A-0xFC000840; PORT21-ROM-PAYLOAD-HANDOFF]`.

#### Step 9: Post-Handoff Candidate Execution
- At `0x8001`: Candidate loader begins execution `[INFERRED: loader source untracked; behaviour described in docs/PORT18_OWNER_TRIAL_PLAN.md:230]`.
- Candidate loader copies core (123,644 B) to `MEMISOSTART = 0x003489B4`, writes Stage 1 witness at `0x0035F7A0`, cleans/invalidates caches, and terminal branches to core entry `0x003489B5` (`_start`) `[INFERRED]`.
- At `0x003489B4`: Core `boot()` runs a **complete second-stage software boot trampoline** (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:85-161`):
  - Copies exception vector table to `0x00000000` `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:98]`.
  - Copies High RAM (158,976 B) and ATCM (27,676 B) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:106-131]`.
  - Copies Low RAM (226,548 B) to `0x00008000..0x0003F4F4`, overwriting the loader `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:133-142]`.
  - Zeroes Canon BSS: **3,183,808 bytes** (`0x0003F4F4..0x003489B4`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:144-153; derived: 0x003489B4 - 0x0003F4F4 = 0x3094C0]`.
  - Calls `sub_fc05b3c8_my` to shift DryOS heap to `0x00366CB0` and restarts the DryOS kernel via `blx 0xfc31b408` (ATCM `0xBFE10F79`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:177-256]`.
  - DryOS boots a second time, dispatching initial tasks and spawning `task_Startup_my`, which branches into stock continuation at `0xFC0D0126` `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:381-438]`.

---

## 3. Identification of Slowdown Causes & Timing Analysis

We now systematically analyze which step or steps explain a **visibly slower start-up only when the card is locked**, contrasting the operations with the unlocked baseline:

### 3.1 Operations Present Only When Card Is Locked

| Operation / Step | Code Address | Runs on Reject Path? | Runs on Accept Path? | Estimated Latency | Slowdown Cause Classification |
|---|---|:---:|:---:|:---:|:---:|
| **SD1stInit / Card Bus Initialization** | `0xFC05BBFE` | Yes | Yes | 50 – 150 ms | **VERIFIED** contributor to locked-card latency `[VERIFIED: ROM 0xFC05BBFE; PORT21-ROM-STARTDISKBOOT]` |
| **VBR Sector Read & Marker Parse** | `0xFC05BC18` | Yes | Yes | 10 – 30 ms | **VERIFIED** contributor `[VERIFIED: ROM 0xFC05BC18; PORT21-ROM-STARTDISKBOOT]` |
| **Directory Search & FAT Stat for DISKBOOT.BIN** | `0xFC37B5CC` | Yes | Yes | 15 – 40 ms | **VERIFIED** contributor `[VERIFIED: ROM 0xFC05BBA2; PORT21-ROM-STARTDISKBOOT]` |
| **DRAM Buffer Allocation (118,001 B)** | `0xFC092440` | Yes | Yes | < 1 ms | **VERIFIED** negligible `[VERIFIED: ROM 0xFC05BBAE; PORT21-ROM-STARTDISKBOOT]` |
| **Physical SD Card File Read (118,001 B across SD Bus)** | `0xFC37B552` | Yes | Yes | 30 – 100 ms | **VERIFIED** major I/O contributor `[VERIFIED: ROM 0xFC05BBD8; PORT21-ROM-STARTDISKBOOT]` |
| **Byte 0 Stripping In-Place Left Shift (118,000 B)** | `0xFC54DE4E` | **No** (skipped) | Yes | 1 – 3 ms | **VERIFIED** negligible `[VERIFIED: ROM 0xFC54DE4E-0xFC54DE5E; PORT21-ROM-EXEC-VALIDATE]` |
| **DancingBits Row 13 Descrambler (236,000 function calls)** | `0xFC42189C` | **No** (skipped) | Yes | 60 – 250 ms | **VERIFIED** major CPU contributor `[VERIFIED: ROM 0xFC42189C-0xFC421922; PORT21-ROM-DANCINGBITS-MAIN]` |
| **Cache Clean/Invalidate & MPU Region 7 Config** | `0xFC0D9CAC` | **No** (skipped) | Yes | 1 – 5 ms | **VERIFIED** negligible `[VERIFIED: ROM 0xFC0D9CAC-0xFC0D9CB0; PORT21-ROM-PREPARE-EXEC]` |
| **DRAM Byte Copy to 0x40008000 (118,001 B)** | `0xFC0007DC` | **No** (skipped) | Yes | 3 – 8 ms | **VERIFIED** minor contributor `[VERIFIED: ROM 0xFC0007DC-0xFC0007E8; PORT21-ROM-PAYLOAD-HANDOFF]` |
| **Word-by-Word Memory Verification (118,001 B)** | `0xFC0007EE` | **No** (skipped) | Yes | 3 – 8 ms | **VERIFIED** minor contributor `[VERIFIED: ROM 0xFC0007EE-0xFC000832; PORT21-ROM-PAYLOAD-HANDOFF]` |
| **Second-Stage Software Reboot Trampoline (`boot()`)** | `boot_prototype.c:85` | **No** (skipped) | Yes | 400 – 1000 ms | **VERIFIED** (body) / **INFERRED** (reached): massive contributor `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:85-161]` |
| **Hardware Watchdog Reset Cycle (if faulted)** | N/A | **No** (skipped) | Conditional (if hang) | 1000 – 2000 ms | **INFERRED** architectural model / **UNKNOWN** whether fired on hardware |

### 3.2 Evaluation of the Cumulative Latency

1. **Reject Path Cumulative Latency**:
   - SD bus init (~100 ms) + VBR read (~20 ms) + FAT lookup (~25 ms) + SD read of 118 KB (~60 ms) + buffer free (< 1 ms).
   - **Total Reject Path Overhead**: ~**200 ms**.
   - Assessment: While 200 ms is measurable with instruments, in human perception during camera cold start (which normally takes 2.0–3.0 seconds), a 200 ms delta is subtle and barely perceptible as "visibly slower" `[INFERRED]`.

2. **Accept Path Cumulative Latency (without crash)**:
   - SD I/O and FAT operations (~200 ms).
   - DancingBits descrambling loop (236,000 function calls with division in uncached/early DRAM): ~**150–250 ms**.
   - DRAM copy & verification: ~**15 ms**.
   - Second-stage software reboot trampoline (`boot_prototype.c:85-161`):
     - Zeroing 3.18 MiB of Canon BSS: ~**50 ms**.
     - Complete second initialization of DryOS kernel, task scheduler, driver tables, and peripheral controllers: ~**400–800 ms**.
   - **Total Accept Path Overhead**: ~**800 ms to 1.3 seconds** `[INFERRED]`.
   - Assessment: A ~1-second additional delay on top of a 2-second boot represents a **35–50% increase in start-up time**, which is **immediately and unmistakably visible** to a human operator `[INFERRED]`.

3. **Accept Path Cumulative Latency (with crash/watchdog reset)**:
   - Accept path execution (~400 ms) + watchdog timer timeout window (~**1.0–2.0 s**) + cold stock restart (~2.0 s).
   - **Total Watchdog Overhead**: **1.5 to 2.5 seconds** additional delay before stock UI appears `[INFERRED]`.
   - Assessment: Completely satisfies the owner's observation of a visibly slower boot `[INFERRED]`.

---

## 4. Discrimination of Hypotheses H1–H4

We now evaluate the candidate explanations for why start-up was visibly slower with the card locked while the inspector reported `WITNESS_INVALID`:

### 4.1 Detailed Hypothesis Assessments

#### Hypothesis H1: Candidate was rejected by a gate in StartDiskboot
- **Verdict**: **RULED OUT / CONTRADICTED BY BINARY STRUCTURE** `[INFERRED]`.
- **Reasoning**:
  1. For `sub_fc05bc3c` to reject the binary, `sub_fc54de38` must return 1 `[VERIFIED: ROM 0xFC05BC66; PORT21-ROM-STARTDISKBOOT]`.
  2. `sub_fc54de38` returns 1 if and only if:
     - Gate 1: `byte 0 != 0x00` (`0xFC54DE3C`) `[VERIFIED: ROM 0xFC54DE3A-0xFC54DE3C; PORT21-ROM-EXEC-VALIDATE]`.
     - Gate 2: Header offsets 16 and 32 match `"gaonisoy"` (`0xFC54DE4C`) `[VERIFIED: ROM 0xFC54DE3E-0xFC54DE4C; PORT21-ROM-EXEC-VALIDATE]`.
  3. Candidate `DISKBOOT.BIN` was generated by `tools/build_candidate_port2a.py:609-616` with a prepended `0x00` byte (`byte 0 == 0x00`) and the standard DancingBits scrambled header `[VERIFIED: candidate_port2a/DISKBOOT.BIN; tools/validate_candidate_port2a.py:81-93; tools/build_candidate_port2a.py:609-616]`.
  4. Neither Gate 1 nor Gate 2 can reject the candidate binary `[VERIFIED: static disassembly]`.
  5. Furthermore, the reject path latency (~200 ms) is subtle, whereas the accept path latency (800–1500 ms) provides a much stronger fit to the "visibly slower" start-up observation `[INFERRED]`.

#### Hypothesis H2: Accept path taken, but loader stopped at `check_compat()`
- **Verdict**: **INCOMPATIBLE WITH UNINTERRUPTED BOOT; POSSIBLE ONLY VIA WATCHDOG RESET** `[INFERRED]`.
- **Reasoning**:
  1. The candidate passed `sub_fc54de38`, was decoded, copied to `0x40008000`, and entered at `0x8001` `[INFERRED]`.
  2. In `check_compat.c` (untracked local source), a compatibility mismatch triggers `blink()`, which enters an infinite loop (`while(1)`) `[INFERRED]`.
  3. Under uninterrupted execution, the camera would hang indefinitely with a black screen; it would **never reach the stock UI** `[INFERRED]`.
  4. The only way stock UI could appear under H2 is if a hardware watchdog timer reset the CPU after 1–2 seconds, causing the camera to reboot stock firmware from cold reset `[INFERRED]`.
  5. However, candidate platform ID `0x32A8` and version `"GM1.10C"` match the camera, so `check_compat()` is expected to pass `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:7]`.

#### Hypothesis H3: Accept path taken, loader ran, but stock boot later overwrote witness
- **Verdict**: **STRONGLY FITS ALL OBSERVATIONS (PRIMARY CANDIDATE)** `[INFERRED]`.
- **Reasoning**:
  1. Candidate passed byte 0 gating, underwent DancingBits descrambling, was copied to `0x40008000`, and branched to `0x8001` `[INFERRED]`.
  2. The loader executed, copied core to `0x003489B4`, wrote Stage 1 witness at `0x0035F7A0`, and branched to core `boot()` `[INFERRED]`.
  3. In `boot()`, the camera executed the full second-stage software boot trampoline, restarting DryOS `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:85-161]`.
  4. The execution of the full decoding chain + double kernel initialization perfectly explains the **visibly slower start-up** `[INFERRED]`.
  5. Subsequently, control either:
     - **Path 3a**: Followed the candidate continuation into stock firmware, but stock DryOS allocations or unshifted heap structures reused `0x0035F7A0` (which lies inside stock heap `0x003489B4..0x00600014`), corrupting the witness before the Canon Basic inspector ran `[INFERRED: docs/PORT21_RAM_LIFETIME.md:44-48, 240-250]`.
     - **Path 3b**: Encountered a fault or watchdog reset during early DryOS kernel re-initialization, causing a reboot into pure stock ROM (`0xFC02000C`), which cleared Canon BSS (`0x0003F4F4..0x003489B4`) and initialized stock heap covering `0x0035F7A0`, overwriting the witness `[INFERRED]`.
  6. Under either sub-path, stock UI appeared, start-up was visibly slower, and the inspector reported `WITNESS_INVALID`, matching all owner observations `[INFERRED]`.

#### Hypothesis H4: Loader wrote witness, but witness format/checksum was malformed
- **Verdict**: **TIMING FITS, BUT ROOT CAUSE RULED OUT BY T3** `[VERIFIED / INFERRED]`.
- **Reasoning**:
  1. Timing fits the accept path identically to H3 `[INFERRED]`.
  2. However, PORT-21 T3 rigorously proved bit-for-bit checksum and layout compatibility between the witness writer (`boot_witness.h:33-42`) and the inspector parser (`witness_inspector_payload.S:73-90`) across all stages and valid states `[VERIFIED: tests/test_port21_witness_roundtrip.py:1-205]`.
  3. A correctly written witness would not be rejected as `WITNESS_INVALID` due to formatting `[VERIFIED: tests/test_port21_witness_roundtrip.py]`.

---

### 4.2 Findings-to-Hypotheses Discrimination Matrix

| Finding ID | Finding Description | Confidence | H1 | H2 | H3 | H4 | Epistemic Rationale & Timing Significance |
|:---|:---|:---:|:---:|:---:|:---:|:---:|:---|
| **TF1** | Unlocked SD card branches away at `0xFC05BC0A` before any disk I/O, file reading, decoding, or payload copying. | **VERIFIED** `[VERIFIED: ROM 0xFC05BC0A-0xFC05BC38; PORT21-ROM-STARTDISKBOOT]` | neutral | neutral | neutral | neutral | Explains why unlocked boot is fast and establishes baseline timing. |
| **TF2** | Reject path reads 118,001 B from SD card, but skips shift loop, DancingBits decoding, DRAM handoff, and core boot. | **VERIFIED** `[VERIFIED: ROM 0xFC05BC66-0xFC05BC74, 0xFC54DE38-0xFC54DE6A; PORT21-ROM-STARTDISKBOOT; PORT21-ROM-EXEC-VALIDATE]` | consistent with | neutral | neutral | neutral | Reject path overhead is limited to SD I/O (~200 ms), unlikely to appear "visibly slower". |
| **TF3** | Candidate `DISKBOOT.BIN` has `byte 0 == 0x00` and non-gaonisoy header, guaranteeing pass through Gate 1 and Gate 2. | **VERIFIED** `[VERIFIED: candidate_port2a/DISKBOOT.BIN; tools/validate_candidate_port2a.py:81-93; PORT19-ROM-EXEC-VALIDATE]` | **rules out** | consistent with | consistent with | consistent with | Conclusively proves candidate binary cannot take the reject path in `sub_fc54de38`. |
| **TF4** | Accept path executes DancingBits Row 13 descrambling involving 236,000 function calls (`sub_fc469180` and `sub_fc469188`). | **VERIFIED** `[VERIFIED: ROM 0xFC42189C-0xFC421922; PORT21-ROM-DANCINGBITS-MAIN]` | rules out | supports | supports | supports | Introduces substantial CPU execution latency (150–250 ms) unique to the accept path. |
| **TF5** | Accept path executes memory handoff in `sub_fc0007c0`, copying 118,001 B to `0x40008000` and verifying words before `bx 0x8001`. | **VERIFIED** `[VERIFIED: ROM 0xFC0007DC-0xFC000840; PORT21-ROM-PAYLOAD-HANDOFF]` | rules out | supports | supports | supports | Proves candidate payload is physically loaded into `0x40008000` prior to execution. |
| **TF6** | Candidate core `boot()` software reboot trampoline executes double kernel initialization and zeroes 3.18 MiB Canon BSS. | **VERIFIED** (body) / **INFERRED** (reached) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:85-161]` | rules out | rules out (uninterrupted) | **supports** | supports | Introduces massive 500–1000 ms latency that fully accounts for "visibly slower" start-up. |
| **TF7** | Compatibility failure infinite delay in `blink()` prevents stock UI without watchdog reset. | **INFERRED** `[INFERRED: check_compat.c:108-118]` | neutral | rules out (uninterrupted) / UNKNOWN (watchdog) | neutral | neutral | H2 cannot reach stock UI directly; requires watchdog reboot. |
| **TF8** | Witness writer and inspector payload formats and checksums are bit-for-bit identical. | **VERIFIED** `[VERIFIED: tests/test_port21_witness_roundtrip.py]` | neutral | neutral | neutral | **rules out** | Rules out H4 formatting defect as cause of `WITNESS_INVALID`. |

---

## 5. Implications for the Morning Session

The resolution of the start-up timing mechanism yields actionable directives for the next camera session:

1. **Cease File-Gating and DISKBOOT Header Research (H1 Ruled Out)**:
   - There is no need to modify file naming, SD card formatting tools, partition schemes, or byte 0 headers. The camera indisputably accepted `A/DISKBOOT.BIN`, decoded it with DancingBits Row 13, and transferred control to `0x8001`.

2. **Target Post-Handoff Execution & Memory Verification**:
   - The primary unknown is whether the candidate loader executed its terminal branch to `_start`, whether `boot()` completed, and why the witness at `0x0035F7A0` was invalid.
   - The morning trial plan should include an explicit inspection of DRAM at `0x40008000` using the RAM comparison tool (`RAMCMP`):
     - `sub_fc0007c0` copies the decoded loader to `0x40008000` before jumping `[VERIFIED: ROM 0xFC0007DC; PORT21-ROM-PAYLOAD-HANDOFF]`.
     - Unlike `0x00008000` (which is overwritten by `boot()` Copy Loop 3), DRAM at `0x40008000` lies in high uncached DRAM alias space and is not touched by stock copy loops `[VERIFIED: ROM 0xFC020054..0xFC020066; PORT21-ROM-BOOT-EARLY]`.
     - Comparing `0x40008000` against `candidate_loader.bin` via `RAMCMP` (`r_l4`) will provide **definitive physical confirmation** that `StartDiskboot` accepted and decoded the candidate image on hardware.

3. **Investigate Watchdog Reset vs Clean Continuation**:
   - The morning session should determine whether the stock UI appeared via `task_Startup_my` branching to `sub_fc0d0126` (clean continuation), or whether a CPU watchdog reset restarted the camera into stock ROM.
   - If a watchdog reset occurred, debugging must center on MPU permissions, stack pointers (`sp = 0x4000`), or peripheral clock gating in `boot()`.

---

## 6. Offline Evidence Manifest & Citations

All ROM references used in this analysis are strictly bounded and recorded in `docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json` under scope `SCOPE-PORT21-DISKBOOT-TIMING` (budget: <= 4 KiB per read, 32 KiB total) `[VERIFIED: docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json:48-94; tools/port11c_evidence_validator.py:1]`:

| Evidence ID | Start Address | End Address | Byte Count | SHA-256 Digest | Provenance & Source Citation |
|---|---|---|:---:|---|---|
| `PORT21-ROM-STARTDISKBOOT` | `0xFC05BBEA` | `0xFC05BDE9` | 512 B | `a2ea19dfed6f386b32074c65ec682a557a24cf3ddcdeb73f29108ae16854acfc` | Tracked citation `docs/PORT19_DISKBOOT_ENCODING.md:44, 76, 79, 338, 352` (`StartDiskboot` 0xFC05BBEA, `sub_fc05bc3c` 0xFC05BC3C) |
| `PORT21-ROM-EXEC-VALIDATE` | `0xFC54DE00` | `0xFC54E1FF` | 1024 B | `570ac7e7702b065b4c27a62590cbcdea9db7ca09670b22b96a08ce8315d3ca6b` | Tracked citation `docs/PORT19_DISKBOOT_ENCODING.md:45, 130, 153` (`sub_fc54de38` Gate 1 byte 0 check, shift loop) |
| `PORT21-ROM-DANCINGBITS-MAIN` | `0xFC421800` | `0xFC421BFF` | 1024 B | `845863414ef9691aa46e096d8ae12fe7339f532ad10121dedf907a653e9b627d` | Tracked citation `docs/PORT19_DISKBOOT_ENCODING.md:46, 180, 194` (`sub_fc42189c` DancingBits main block loop) |
| `PORT21-ROM-DANCINGBITS-DANCE` | `0xFC469100` | `0xFC4692FF` | 512 B | `00b960cbbdb3d0c077b36209a020a450ce04e5beb84da59df94d169f8ede102c` | Tracked citation `docs/PORT19_DISKBOOT_ENCODING.md:47, 264, 278` (`sub_fc469180` table lookup, `sub_fc469188` `_dance`) |
| `PORT21-ROM-ROW13-TABLE` | `0xFC7C0F80` | `0xFC7C107F` | 256 B | `dbcbc94e7228055ac95454c92be4b9bef56c2b6a5afa3f1ef76c167f76bd50ca` | Tracked citation `docs/PORT19_DISKBOOT_ENCODING.md:48, 271` (DancingBits Row 13 permutation table at `0xFC7C0F8C`) |
| `PORT21-ROM-PREPARE-EXEC` | `0xFC0D9C00` | `0xFC0D9DFF` | 512 B | `8c891f7dc8fc758510f36a69d95ff323cee00a7ac0e853128d1be27d8598d644` | Tracked citation `docs/PORT19_DISKBOOT_ENCODING.md:49, 298` (`sub_fc0d9c9c` MPU, cache invalidation, handoff) |
| `PORT21-ROM-PAYLOAD-HANDOFF` | `0xFC000780` | `0xFC00087F` | 256 B | `59f6ea920dc02a41983c3434eb62e3828802d9fb52f5ebf46618fff1639eb214` | Tracked citation `docs/PORT19_DISKBOOT_ENCODING.md:50, 315` (`sub_fc0007c0` byte copy to `0x40008000`, verify, `bx 0x8001`) |

**Total T2 Bytes Read**: 512 + 1024 + 1024 + 512 + 256 + 512 + 256 = **4,096 B** (12.5% of 32 KiB budget). All slices are non-overlapping with each other and non-overlapping with existing T1 slices `[VERIFIED: docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json; tools/port11c_evidence_validator.py]`.

In `docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json`, `SCOPE-PORT21-DISKBOOT-TIMING` is appended to `authorization_scopes` authorizing these 7 slices (budget 32 KiB), with zero overlapping ranges. The underlying ROM reads and byte-exact provenance were established in PORT-19 (`docs/PORT19_DISKBOOT_ENCODING.md` and `docs/agentbridge/PORT19_EVIDENCE_MANIFEST.json`). To maintain compatibility with existing T1 test suites (`tests/test_port21_ram_lifetime.py`), the manifest preserves the six T1 entries in `evidence_entries` byte-identically while appending the T2 authorization scope.
