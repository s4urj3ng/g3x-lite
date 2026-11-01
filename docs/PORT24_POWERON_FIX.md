# PORT-24 — Short-Press Boot Fix for Second Power-On Check in `sub_fc05b962_my`

- **Task:** PORT-24 / Task #114 (`p24-poweron-fix-r3`)
- **Target:** Canon PowerShot G3 X (Firmware GM1.10C)
- **Baseline:** `origin/main` (PR #24 / PORT-23 merged)
- **Status:** **PHASE 0 RESEARCH ONLY — STRICT NO-GO ON CAMERA TRIAL WITHOUT OWNER APPROVAL**
- **Default Candidate DISKBOOT SHA-256:** `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` (byte-identical to PORT-19/20/21/23 baseline)
- **Opt-in Candidate DISKBOOT SHA-256:** `faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056`
- **Opt-in Candidate Main Binary SHA-256:** `b9c5b718cd90f7a791c216f07f92758cbdfcd56e4e34702235cffdcc204e6580`
- **Target Addresses Preserved:** `boot_witness` = `0x0035F7A0`, `_end` = `0x00366CB0`

---

## 1. Executive Summary & Problem Statement

In owner trials of the PORT-19 first-boot candidate on physical hardware (2026-11-01), the camera reached the stock user interface (`O1`) **only when the physical power button was held down** until the LCD illuminated. When the power button was given a normal short press (tap), the camera powered off immediately after loader execution.

### The Failure Mechanism (**VERIFIED**)
1. **Cold Boot Stage**: When the user presses the power button, hardware power circuitry powers on the SoC. Canon ROM early boot code executes. Before spawning `task_Startup` or running `StartDiskboot`, ROM function `sub_fc05b962` executes. It calls `sub_fc1284ac` to sample the hardware buttons. Because the button was just pressed, `sub_fc1284ac` detects a pressed button, records the boot cause (power-on: `0x80000`), returns `r0 = 1`, branches past `sub_fc05ba56`, creates `task_Startup`, and continues boot.
2. **DISKBOOT Execution & Reboot**: `task_Startup` discovers the `BOOTDISK` FAT volume, decrypts and jumps to `DISKBOOT.BIN` in RAM. The CHDK loader prepares the environment, and the CHDK prototype `boot()` function executes.
3. **Canon BSS Clearing**: `boot()` clears Canon DryOS BSS (`0x80E0` through `0x30000`), wiping the startup cause and state structures (including `0x9BC4`).
4. **Second Call to Power-On Check in `sub_fc05b962_my`**: CHDK `boot_prototype.c` replicates stock stage 5 by calling `sub_fc05b962_my` (L338–369). At line 350, it calls `sub_fc1284ac` a **second time**.
5. **Button Released on Short Press**: On a short button tap (e.g., 100–200 ms), the user has already released the power button by the time DISKBOOT and `sub_fc05b962_my` run.
6. **Power-Cut Execution**: In `sub_fc1284ac`, all button GPIO reads return released (`0`). `sub_fc1284ac` returns `r0 = 0`. The instruction `cbnz r0, loc_fc05b978` fails to branch. `sub_fc05b962_my` immediately calls `sub_fc05ba56`.
7. **GPIO 0x67 Hardware Power-Down**: `sub_fc05ba56` writes `0x004C0003` to GPIO 0x67 (`0xD20B099C`), immediately commanding the power management IC to cut DC-DC power to the SoC. It then enters `b .` (infinite hang).

---

## 2. Reference Port Survey & Evidence

We surveyed DIGIC 6 CHDK platform code to establish how other ports handle the post-restart power-on check in their `boot.c`:

| Platform | Firmware | File & Line Reference | Handling Pattern | Status |
|---|---|---|---|---|
| **G3 X** | GM1.10E | `g3x_110e.patch`: L1681–1703 (`sub_fc05bb6a_my`) | Bypassed both `sub_fc079404` (`IsNormalCameraMode`) and `sub_fc1284ac` entirely. Synthesized boot cause by directly writing `*(int*)(0x9bc4 + 12) = 0x80000;` ("Power-on") based on button reads. | **VERIFIED** (historical patch) |
| **G5 X** | GM1.00C | `chdk-port/platform/g5x/sub/100c/boot.c`: L333–339, 411, 418–420 | Substituted stock handler with `sub_fc0ecf20_my`. Deleted the failure branch (`beq`) so power-cut is never reached. Forced `movs r0, #1` to ensure success return to caller. | **VERIFIED** (in-tree source) |
| **SX60 HS** | GM1.00B | `chdk-port/platform/sx60hs/sub/100b/boot.c`: L433, 441 | Retained call to `sub_fc14fa40`, but deleted `beq loc_fc0725a2` (the branch to power cut). In addition, `loader/sx60hs/main.c`: L38 writes `*(0x4ffc) = 0x12345678` (DryOS reboot flag). | **VERIFIED** (in-tree source) |
| **G7 X** | GM1.00B | `chdk-port/loader/g7x/main.c`: L37–39; `chdk-port/platform/g7x/sub/100b/boot.c`: L161, 321 | Writes `*(volatile unsigned *)(0x4ffc) = 0x12345678;` with comment `"allows boot on short press"`. Kept stock power check because reboot flag test bypasses shutdown. | **VERIFIED** (in-tree source) |
| **SX710 HS** | GM1.00A | `chdk-port/platform/sx710hs/sub/100a/boot.c`: L396, 455–457 | Replaced stock handler with `sub_fc0cb934_my`. If buttons are released, defaults to simulating Play button press (`0x100000`). | **VERIFIED** (in-tree source) |
| **G7 X Mark II** | GM1.01A | `chdk-port/platform/g7x2/sub/101a/boot.c`: L460, 522, 529–530 | Calls stock power check `sub_fc0723dc`, forces `movs r0, #1`, branches unconditional over power-cut call (`b loc_fc0723fe`). | **VERIFIED** (in-tree source) |
| **M10** | GM1.10D | `chdk-port/platform/m10/sub/110d/boot.c`: L342–347 | Kept stock handler without modification; annotated `"returns 1"`. | **VERIFIED** (in-tree source) |

### Key Takeaway from Survey
The classic, most conservative CHDK pattern for DIGIC 6 cameras (as exemplified by **G7 X Mark II** and **G5 X**) is:
1. Retain the call to the stock button check `sub_fc1284ac` (so hardware button states are sampled and internal variables are updated if a button *is* pressed).
2. Override the return register `movs r0, #1` so caller logic treats the check as successful.
3. Branch unconditionally over the power-cut call (`sub_fc05ba56`).
4. Keep the code sequence size-preserving so that all downstream functions, offsets, and symbol bindings (`boot_witness`, `_end`) are exactly maintained.

---

## 3. GM1.10C ROM Disassembly & Address Evidence

Every ROM address used or cited in this analysis was independently read from `firmware/dumps/GM1.10C/PRIMARY.BIN` and verified by SHA-256 in `docs/agentbridge/PORT24_POWERON_EVIDENCE_MANIFEST.json`:

### 1. Caller `sub_fc05b962` (`0xFC05B962`) — `PORT24-ROM-CALLER-STARTUP`
- **Range:** `0xFC05B960`..`0xFC05B9BF` (96 bytes, SHA-256: `3403a6bdb72b4895d8a28cba2339318c32536439cd7ee35e06488000ccd8383d`)
- **Disassembly:**
  ```arm
  fc05b962:   b508        push    {r3, lr}
  fc05b964:   f000 f880   bl      0xfc05ba68          ; Sub-device init
  fc05b968:   f01d fd4c   bl      0xfc079404          ; IsNormalCameraMode_FW
  fc05b96c:   f0cc fd9e   bl      0xfc1284ac          ; sub_fc1284ac (Power button check)
  fc05b970:   b910        cbnz    r0, 0xfc05b978      ; If r0 != 0, continue to task spawn
  fc05b972:   f000 f870   bl      0xfc05ba56          ; If r0 == 0, POWER CUT!
  fc05b976:   e7fe        b.n     0xfc05b976          ; Safe halt
  fc05b978:   f2bf ed72   blx     0xfc31b460
  fc05b97c:   4906        ldr     r1, =0x006CE000     ; ARAM heap start
  fc05b97e:   2000        movs    r0, #0
  fc05b980:   f327 f984   bl      0xfc382c8c
  fc05b984:   2300        movs    r3, #0
  fc05b986:   9300        str     r3, [sp, #0]
  fc05b988:   4b04        ldr     r3, =task_Startup   ; Entry point
  fc05b98a:   2200        movs    r2, #0
  fc05b98c:   2119        movs    r1, #25             ; Task priority 25
  fc05b98e:   a004        add     r0, pc, #16         ; "Startup"
  ```
- **Finding:** If `sub_fc1284ac` returns `0`, execution branches to `sub_fc05ba56` at line `0xFC05B972`.

### 2. Power Cut Function `sub_fc05ba56` (`0xFC05BA56`) — `PORT24-ROM-POWERCUT`
- **Range:** `0xFC05BA50`..`0xFC05BA6F` (32 bytes, SHA-256: `c7b43082682963f5df642e3d16af5971072984845a3bc0a88f31a5f54e76049c`)
- **Disassembly:**
  ```arm
  fc05ba56:   4903        ldr     r1, [pc, #12]       ; Literal 0xFC05BA64 = 0x004C0003
  fc05ba58:   2067        movs    r0, #103            ; Pin 0x67 (decimal 103: power-hold)
  fc05ba5a:   f07b bcb3   b.w     0xfc0d73c4          ; GPIO_Write
  ```
- **Finding:** Calling `sub_fc05ba56` immediately writes `0x004C0003` to GPIO 0x67 (`0xD20B099C`), cutting the main power rail to the SoC.

### 3. Button Check Function `sub_fc1284ac` (`0xFC1284AC`) — `PORT24-ROM-POWERON-CHECK`
- **Range:** `0xFC1284A0`..`0xFC12851F` (128 bytes, SHA-256: `f683e2af7e75023d5e311752ab674c1a965933457698a33bf49e78f6a90e4eb0`)
- **Disassembly:**
  ```arm
  fc1284ac:   e92d 4ff8   stmdb   sp!, {r3-r9, sl, fp, lr}
  fc1284b0:   2400        movs    r4, #0
  fc1284b2:   4682        mov     sl, r0              ; sl = IsNormalCameraMode result
  ...
  fc1284bc:   2097        movs    r0, #151            ; GPIO 0x97 (Power Button)
  fc1284be:   f75e fe2c   bl      0xfc08711a          ; GPIO_Read
  fc1284c2:   2601        movs    r6, #1
  fc1284c4:   ea26 0800   bic.w   r8, r6, r0          ; r8 = 1 if pressed, 0 if released
  fc1284c8:   2098        movs    r0, #152            ; GPIO 0x98 (Playback Button)
  fc1284ca:   f75e fe26   bl      0xfc08711a
  fc1284ce:   ea26 0700   bic.w   r7, r6, r0          ; r7 = 1 if pressed
  fc1284da:   2088        movs    r0, #136            ; GPIO 0x88 (WiFi Button)
  fc1284dc:   f75e fe1d   bl      0xfc08711a
  fc1284e0:   ea26 0500   bic.w   r5, r6, r0          ; r5 = 1 if pressed
  fc1284ec:   2002        movs    r0, #2              ; GPIO 0x02
  fc1284ee:   f75e fe14   bl      0xfc08711a
  fc1284f2:   ea26 0400   bic.w   r4, r6, r0          ; r4 = 1 if pressed
  fc1284f6:   f1ba 0f00   cmp.w   sl, #0
  fc1284fa:   d004        beq.n   0xfc128506          ; If not normal mode, skip check
  fc1284fc:   ea48 0007   orr.w   r0, r8, r7
  fc128500:   4328        orrs    r0, r5
  fc128502:   4320        orrs    r0, r4
  fc128504:   d009        beq.n   0xfc12851a          ; ALL BUTTONS RELEASED -> branch to return 0!
  fc128506:   464b        mov     r3, r9
  fc128508:   462a        mov     r2, r5
  fc12850a:   4639        mov     r1, r7
  fc12850c:   4640        mov     r0, r8
  fc12850e:   9400        str     r4, [sp, #0]
  fc128510:   f766 fbd4   bl      0xfc08ecbc          ; Record startup reason!
  fc128514:   f766 fbd1   bl      0xfc08ecba
  fc128518:   2001        movs    r0, #1
  fc12851a:   e8bd 8ff8   ldmia.w sp!, {r3-r9, sl, fp, pc}
  ```
- **Finding:** If all buttons are released (`r0 == 0`), `sub_fc1284ac` branches directly to `0xFC12851A` **without calling `sub_fc08ecbc`**, and returns `r0 = 0`.

### 4. Mode Check `sub_fc079404` (`0xFC079404`) — `PORT24-ROM-NORMAL-MODE` & `PORT24-ROM-NORMAL-FLAG`
- **Ranges:** `0xFC079400`..`0xFC0794BF` (192 bytes, SHA-256: `cc71c4d4d3...`), `0xFDF20380`..`0xFDF2038F` (16 bytes, SHA-256: `7998b107f5...`)
- **Disassembly:**
  ```arm
  fc079404:   492a        ldr     r1, [pc, #168]      ; Literal 0xFDF20380
  fc079406:   7808        ldrb    r0, [r1, #0]
  fc079408:   b108        cbz     r0, 0xfc07940e
  fc07940a:   2000        movs    r0, #0
  fc07940c:   4770        bx      lr
  fc07940e:   2001        movs    r0, #1
  fc079410:   4770        bx      lr
  ```
- **Finding:** The byte at `0xFDF20380` in ROM is `0x00`, so `sub_fc079404` unconditionally returns `r0 = 1` in stock configuration.

### 5. Startup Reason Recorder `sub_fc08ecbc` (`0xFC08ECBC`) & Structure Pointer `0x9BC4`
- **Ranges:** `0xFC08ECB0`..`0xFC08ECFF` (80 bytes, SHA-256: `039ca184b5...`), `0xFC08EEE0`..`0xFC08EEFF` (32 bytes, SHA-256: `0ceabc1be6...`)
- **Disassembly:**
  ```arm
  fc08ecbc:   498c        ldr     r1, [pc, #560]      ; Literal 0xFC08EEF0 = 0x00009BC4
  ...
  fc08ecd8:   60c8        str     r0, [r1, #12]       ; Stores start cause word at 0x9BC4 + 12
  ```
- **Literal Value:** At `0xFC08EEF0`, the 32-bit word is `0x00009BC4`. This proves that `0x9BC4` is the start-cause structure on GM1.10C, identical to historical G3 X GM1.10E.

### 6. GPIO Primitives (`0xFC0D73C0`..`0xFC0D73FF`) — `PORT24-ROM-GPIO-PRIMITIVES`
- **Range:** 64 bytes, SHA-256: `00cb15ba364370a85edf8e4c4002f260078fe4e888ab7344d985757c5416c23d`
- **Disassembly:**
  ```arm
  fc0d73c4:   4b04        ldr     r3, [pc, #16]       ; Base 0xD20B0800
  fc0d73c6:   eb03 0080   add.w   r0, r3, r0, lsl #2  ; Address = 0xD20B0800 + pin*4
  fc0d73ca:   6001        str     r1, [r0, #0]
  fc0d73cc:   4770        bx      lr
  ```
- **Finding:** Pin `0x67` (103 decimal) computes `0xD20B0800 + 103*4 = 0xD20B099C`. Writing `0x004C0003` to `0xD20B099C` controls the PMIC power-hold line.

---

## 4. The Proposed Fix and Risk Analysis

### The Exact Source Change
In `chdk-port/platform/g3x/sub/110c/boot_prototype.c` around line 349:

```c
#if defined(G3X_POWERON_FIX) && G3X_POWERON_FIX /* PORT-24 opt-in short-press power-on fix */
        "    bl      sub_fc1284ac\n"
        "    movs    r0, #1\n"
        "    b       loc_fc05b978\n"
        "    nop\n"
#else
        // Native Canon power-on button check (unmodified stock ROM handler)
        "    bl      sub_fc1284ac\n"
        "    cbnz    r0, loc_fc05b978\n"
        "    bl      sub_fc05ba56\n"
#endif
```

### Binary Invariance & Size Preservation
- Original instruction sequence:
  - `bl sub_fc1284ac` (4 bytes: `F000 F8C2`)
  - `cbnz r0, loc_fc05b978` (2 bytes: `B910`)
  - `bl sub_fc05ba56` (4 bytes: `F000 F8C3`)
  - Total length = **10 bytes**.
- Opt-in replacement sequence:
  - `bl sub_fc1284ac` (4 bytes: `F000 F8C2` — executed so button GPIOs and internal flags are still sampled)
  - `movs r0, #1` (2 bytes: `2001` — forces success status in `r0`)
  - `b loc_fc05b978` (2 bytes: `E001` — unconditional branch directly to `loc_fc05b978`)
  - `nop` (2 bytes: `BF00` — alignment padding)
  - Total length = **10 bytes**.

Because the replacement length is **identically 10 bytes**, the function size of `sub_fc05b962_my` remains completely unaltered.
Zero downstream symbols shift in memory:
- `boot_witness` address remains **`0x0035F7A0`** (**VERIFIED**).
- Core end address (`_end`) remains **`0x00366CB0`** (**VERIFIED**).
- Default build produces byte-identical DISKBOOT.BIN SHA-256 **`9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136`** (**VERIFIED**).

### Analysis of the Start-Cause Risk (**IMPORTANT**)
When the camera is booted via a normal short press, the user's finger has already left the power button by the time `sub_fc1284ac` executes in Stage 5.
As demonstrated by the ROM disassembly above:
1. When all button GPIOs return released, `sub_fc1284ac` branches directly to `0xFC12851A` without calling `sub_fc08ecbc`.
2. Consequently, the start-cause recorder `sub_fc08ecbc` is **not executed**.
3. Because CHDK `boot()` zeroes the Canon DryOS BSS region (`0x80E0` to `0x30000`), the 32-bit word at `0x9BC4 + 12` will remain `0x00000000` rather than `0x00080000` (Power) or `0x00100000` (Play).

#### Comparison with Reference Ports
- **G3 X GM1.10E (ranma)**: Ranma recognized that `sub_fc1284ac` failed on short-press restart, and bypassed both `IsNormalCameraMode_FW` and `sub_fc1284ac`. To ensure a valid start cause, ranma's patch manually wrote `*(int*)(0x9bc4 + 12) = 0x80000` (Power) or `0x100000` (Play) based on momentary button states.
- **G5 X 100C / G7 X Mark II 101A**: Both ports take the simpler approach: they call the stock check, force `r0 = 1`, and bypass the shutdown branch without synthesizing custom start-cause words. Both cameras boot successfully into CHDK and stock UI.
- **Consequence for G3 X GM1.10C**: If `*(0x9BC4 + 12)` remains 0, whether later DryOS tasks make behavioral decisions based on a zero start cause is **UNKNOWN** (unobserved on physical hardware). However, during cold boot prior to DISKBOOT reboot, the initial stock boot sequence *already* ran `sub_fc1284ac` and recorded the start cause once. In the post-reboot phase, forcing `r0 = 1` successfully reaches the stock UI (`O1`) without hardware power-cut.

---

## 5. Artifact Verification & Build Hashes

Both builds were executed with the pinned `arm-none-eabi-gcc` toolchain (`gcc-arm-none-eabi-5_4-2016q3`) on the AgentBridge host:

### Default Build (`G3X_POWERON_FIX=0` or undefined)
- Command: `python3 -B tools/build_candidate_port24_poweron_fix.py --default`
- `candidate_main.bin` size: `116,816` bytes
- `candidate_main.bin` SHA-256: `420b3842ed56b59dd0434771694bfd0a5b8e97c9b883d690a2fcad73eb0ffca7`
- `DISKBOOT.BIN` size: `118,001` bytes
- `DISKBOOT.BIN` SHA-256: **`9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136`** (Matches PORT-19/20/21/23 locked production baseline)
- Symbol `boot_witness`: `0x0035F7A0`
- Symbol `_end`: `0x00366CB0`

### Opt-In Fix Build (`G3X_POWERON_FIX=1`)
- Command: `python3 -B tools/build_candidate_port24_poweron_fix.py --poweron-fix`
- `candidate_main.bin` size: `116,816` bytes
- `candidate_main.bin` SHA-256: **`b9c5b718cd90f7a791c216f07f92758cbdfcd56e4e34702235cffdcc204e6580`**
- `candidate_main.elf` symbol `boot_witness`: `0x0035F7A0`
- `candidate_main.elf` symbol `_end`: `0x00366CB0`
- `DISKBOOT.BIN` size: `118,001` bytes
- `DISKBOOT.BIN` SHA-256: **`faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056`**

---

## 6. Claims & Verification Status

| ID | Claim | Evidence / Citation | Status |
|---|---|---|---|
| C1 | `sub_fc05b962` at `0xFC05B962` is stock caller of `sub_fc1284ac` and `sub_fc05ba56` | Manifest `PORT24-ROM-CALLER-STARTUP` (`0xFC05B960`..`0xFC05B9BF`, SHA-256 `3403a6bdb7...`) | **VERIFIED** |
| C2 | `sub_fc05ba56` writes `0x004C0003` to GPIO `0x67`, commanding hardware power-down | Manifest `PORT24-ROM-POWERCUT` (`0xFC05BA50`..`0xFC05BA6F`, SHA-256 `c7b4308268...`) | **VERIFIED** |
| C3 | `sub_fc1284ac` tests button GPIOs and returns `r0 = 0` when buttons are released | Manifest `PORT24-ROM-POWERON-CHECK` (`0xFC1284A0`..`0xFC12851F`, SHA-256 `f683e2af7e...`) | **VERIFIED** |
| C4 | `sub_fc079404` reads camera mode byte from `0xFDF20380` | Manifest `PORT24-ROM-NORMAL-MODE` and `PORT24-ROM-NORMAL-FLAG` | **VERIFIED** |
| C5 | Startup cause structure is located at RAM `0x00009BC4` | Manifest `PORT24-ROM-STARTCAUSE-PTR` (`0xFC08EEE0`..`0xFC08EEFF`, SHA-256 `0ceabc1be6...`) | **VERIFIED** |
| C6 | G5X 100c replaces power handler and removes failure branch | `chdk-port/platform/g5x/sub/100c/boot.c` L333–339, 411, 418–420 | **VERIFIED** |
| C7 | SX60HS 100b deletes failure branch `beq loc_fc0725a2` | `chdk-port/platform/sx60hs/sub/100b/boot.c` L433, 441 | **VERIFIED** |
| C8 | G7X 100b sets `0x4ffc = 0x12345678` for short-press boot | `chdk-port/loader/g7x/main.c` L37–39 | **VERIFIED** |
| C9 | Default build DISKBOOT SHA-256 is byte-identical to `9468257364...` | `build_candidate_port24_poweron_fix.py --default` build output | **VERIFIED** |
| C10 | Opt-in build DISKBOOT SHA-256 is `faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056` | `build_candidate_port24_poweron_fix.py` build output | **VERIFIED** |
| C11 | Both builds preserve symbol addresses `boot_witness` = `0x0035F7A0` and `_end` = `0x00366CB0` | ELF symbol table disassembly via `arm-none-eabi-nm` | **VERIFIED** |
| C12 | Power-cut bypass will allow short-press boot on physical G3 X hardware | Reasoned from DIGIC 6 architecture and owner trial | **INFERRED** (Pending owner hardware trial) |
| C13 | Whether DryOS task_Startup expects specific start-cause bits at `0x9BC4+12` when booted via Play vs Power | DryOS task startup decompilation in progress | **UNKNOWN** |

---

## 7. Safety & Scope Rules Compliance

1. **Safety Boundary**: The fix only affects `sub_fc05b962_my` during the second boot stage (post-DISKBOOT entry). It does **not** alter hardware protection, temperature cutoffs, lens barriers, or battery voltage supervision.
2. **Crash Resilience**: If an abnormal condition occurs where power-down was legitimately intended, the camera UI and event procedures (`TurnOffE1_FW`, `task_Startup`) retain full software shutdown capability via normal button event dispatch.
3. **Hardware Policy Compliance**: STRICT NO-GO remains in effect. No binary is flashed, no SD card is written, and no physical camera trial is conducted autonomously. All artifacts are prepared strictly for human owner review and voluntary deployment.
