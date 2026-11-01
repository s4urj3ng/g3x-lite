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

In owner trials of the unchanged PORT-19 default build (`DISKBOOT.BIN` SHA-256 `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136`) on physical hardware (2026-11-01), the camera reached the stock user interface (`O1`) **only when the physical power button was held down** until the LCD illuminated. When the power button was given a normal short press (tap), the camera powered off immediately after loader execution.

The O1 result is credited solely to that unchanged PORT-19 default build with held power button. The opt-in short-press candidate (`faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056`) has never been run on physical camera hardware. *(Historical baseline: The preceding statement reflects pre-trial status as of 2026-11-01; it was superseded by the owner trial on 2026-11-02).*

### Owner Trial Result (2026-11-02)
On 2026-11-02, the owner tested the PORT-24 opt-in short-press candidate (`faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056`, 118,001 B, built from `origin/main` `81532bb` with `build_candidate_port24_poweron_fix.py --poweron-fix`):
- **Card Setup**: `extend.m`, `WITNESS.BIN` (`241420a6...`), and `script.req` unchanged from PORT-19; card locked, FAT32, `BOOTDISK` `0x1E0`, `SCRIPT` `0x1F0`.
- **(1) Short press**: No LED, LCD stayed off -> **`O10`** `[VERIFIED: 2026-11-02 owner trial; outcome O10 in tools/port18_trial_report.py:248-256]`.
- **(2) Held press**: Normal LED blink, Canon logo, stock UI, inspector shows `CONT_ATTEMPTED / FRESHNESS_UNVERIFIED`, no `TRACE.LOG` -> **`O1`** `[VERIFIED: 2026-11-02 owner trial; outcome O1 in tools/port18_trial_report.py:92-96]`.

**Trial Conclusion & Relabeling**:
Removing the second `sub_fc1284ac` check in `sub_fc05b962_my` is **VERIFIED insufficient** for a short-press boot (cited from this 2026-11-02 trial, where short press still failed to boot and produced outcome O10 `[VERIFIED: tools/port18_trial_report.py:248-256]`), and the remaining cause of the short-press power-off is **UNKNOWN**.

### The Failure Mechanism (**INFERRED — SUPERSEDED**)
*(Superseded by 2026-11-02 owner trial: removing the second `sub_fc1284ac` check in `sub_fc05b962_my` is **VERIFIED insufficient** for a short-press boot [cite 2026-11-02 trial], and the remaining cause is **UNKNOWN**. The earlier inferred mechanism below is retained for historical context).*
Supported by GM1.10C ROM disassembly and the owner's recorded observation of held-button boot success vs short-press immediate power-off:
1. **Cold Boot Stage**: When the user presses the power button, hardware power circuitry powers on the SoC. Canon ROM early boot code executes. Before spawning `task_Startup` or running `StartDiskboot`, ROM function `sub_fc05b962` executes. It calls `sub_fc1284ac` to sample the hardware buttons. Because the button was just pressed, `sub_fc1284ac` detects a pressed button, records the boot cause (power-on: `0x80000`), returns `r0 = 1`, branches past `sub_fc05ba56`, creates `task_Startup`, and continues boot.
2. **DISKBOOT Execution & Reboot**: `task_Startup` discovers the `BOOTDISK` FAT volume, decrypts and jumps to `DISKBOOT.BIN` in RAM. The CHDK loader prepares the environment, and the CHDK prototype `boot()` function executes.
3. **Low RAM Copy and BSS Clearing in `boot()`**: In `boot_prototype.c:133-153`, `boot()` executes Copy Loop 3 (`boot_prototype.c:133-143`), which copies ROM data from `0xFCE91058` into Low RAM (`0x00008000`..`0x0003F4F4`), and zeroes Canon BSS only at `0x0003F4F4`..`0x003489B4` (`boot_prototype.c:144-153`). The startup cause word address `0x9BD0` (`0x9BC4 + 12`) falls inside the copied data region (`0x00008000`..`0x0003F4F4`), not the zeroed BSS region. Because reading new ROM ranges is not authorized in this revision and the ROM source bytes at `0xFCE91058 + (0x9BD0 - 0x8000)` are not cited in the evidence manifest, the initial value of the start-cause word at `0x9BD0` after `boot()` copied data is **UNKNOWN**.
4. **Second Call to Power-On Check in `sub_fc05b962_my`**: CHDK `boot_prototype.c` replicates stock stage 5 by calling `sub_fc05b962_my` (L338–369). At line 350, it calls `sub_fc1284ac` a **second time**.
5. **Button Released on Short Press**: On a short button tap (e.g., 100–200 ms), the user has already released the power button by the time DISKBOOT and `sub_fc05b962_my` run.
6. **Power-Cut Execution**: In `sub_fc1284ac`, all button GPIO reads return released (`0`). `sub_fc1284ac` returns `r0 = 0`. The instruction `cbnz r0, loc_fc05b978` fails to branch. `sub_fc05b962_my` immediately calls `sub_fc05ba56`.
7. **GPIO 0x67 Hardware Power-Down**: `sub_fc05ba56` writes `0x004C0003` to GPIO 0x67 (`0xD20B099C`), immediately commanding the power management IC to cut DC-DC power to the SoC. It then enters `b .` (infinite hang).

The expected outcome of the opt-in fix (that forcing `r0 = 1` and bypassing `sub_fc05ba56` will allow a short press to boot without holding the button) is **INFERRED**, with the owner's held-button trial serving as primary empirical supporting evidence. *(SUPERSEDED: The 2026-11-02 owner trial proved that removing this check is **VERIFIED insufficient** for a short-press boot [O10 observed], and the remaining cause is **UNKNOWN**).*

---

## 2. Reference Port Survey & Evidence

We surveyed DIGIC 6 CHDK platform code to establish how other ports handle the post-restart power-on check in their `boot.c` and loader code.

### 2.1 In-Tree Baseline Source Citation
In the current repository worktree (verified tracked via `git ls-files`):
- **File:** `chdk-port/platform/g3x/sub/110c/boot_prototype.c`
- **Revision / Commit:** `deda42b8ae7c495250d3176a64cd8c3c2146d96f` (HEAD)
- **Lines 351–354 (default baseline stock ROM button check path):**
  - Line 351: `        // Native Canon power-on button check (unmodified stock ROM handler)`
  - Line 352: `        "    bl      sub_fc1284ac\n"`
  - Line 353: `        "    cbnz    r0, loc_fc05b978\n"`
  - Line 354: `        "    bl      sub_fc05ba56\n"`

### 2.2 External Upstream Reference Port Citations
Because other camera platform directories are excluded from the `g3x-lite` repository worktree, upstream DIGIC 6 reference implementations are cited from the authoritative public CHDK mirror:
- **Repository Mirror URL:** <https://github.com/01luna/CHDK> (mirroring the official CHDK Subversion repository)
- **Pinned Commit SHA:** `21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6` (SVN revision `r5491`)
- **Retrieval Date:** `2026-11-01`

| Platform | Firmware | File & Line Reference | Verbatim Quoted Source | Handling Pattern | Status |
|---|---|---|---|---|---|
| **G5 X** | GM1.00C | `platform/g5x/sub/100c/boot.c`: L411, L418–420 ([URL](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/platform/g5x/sub/100c/boot.c#L411)) | L411: `//"    beq     loc_fc0ecfba\n" // -`<br>L418: `//"    bl      sub_fc09b450\n" // -`<br>L419: `//"    bl      sub_fc09b44e\n" // -`<br>L420: `"    movs    r0, #1\n"` | Replaced callee with `sub_fc0ecf20_my`; commented out failure branch (`beq loc_fc0ecfba`); commented out start-cause recorder calls; forced `movs r0, #1` at return. | **INFERRED** (upstream source inspection) |
| **SX60 HS** | GM1.00B | `platform/sx60hs/sub/100b/boot.c`: L433, L441–443 ([URL](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/platform/sx60hs/sub/100b/boot.c#L433)) | L433: `//"beq.n   loc_fc06037e\n"  // - this check fails and results in shutdown`<br>L441: `//"bl      sub_fc06082a\n"  // - startupchecks`<br>L442: `//"bl      sub_fc060828\n"  // - nullsub`<br>L443: `"movs    r0, #1\n"` | Replaced callee; commented out shutdown branch (`beq.n loc_fc06037e`); commented out startup checks; forced `movs r0, #1` before return. | **INFERRED** (upstream source inspection) |
| **SX710 HS** | GM1.00A | `platform/sx710hs/sub/100a/boot.c`: L455–458, L467 ([URL](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/platform/sx710hs/sub/100a/boot.c#L455-L458)) | L455: `//"    beq     loc_fc0cf15e\n" // old behavior, skip to return if none set`<br>L456: `"    bne     loc_fc0cf14a\n" // new behavior, go to final code if any set`<br>L457: `// otherwise, act as if play was held`<br>L458: `    "mov  r7, #1\n"`<br>L467: `"    movs    r0, #1\n"` | Replaced callee `sub_fc0cb934_my`. If buttons released, simulates Play button press (`mov r7, #1`), calls recorder `sub_fc086a04`, forces `movs r0, #1`. | **INFERRED** (upstream source inspection) |
| **M10** | GM1.10D | `platform/m10/sub/110d/boot.c`: L342–345 ([URL](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/platform/m10/sub/110d/boot.c#L342-L345)) | L342: `"    bl      sub_fc07ea92\n"        // IsNormalCameraMode_FW`<br>L343: `"    bl      sub_fc08c9c8\n"        // returns 1`<br>L344: `"    cbnz    r0, loc_fc06cab0\n"`<br>L345: `"    bl      sub_fc06cb8e\n"        // sets GPIO 0x67"` | Retained stock caller check without modification; annotated `"returns 1"` in stock ROM. | **INFERRED** (upstream source inspection) |
| **G7 X** | GM1.00B | `loader/g7x/main.c`: L37–39 ([URL](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/loader/g7x/main.c#L37-L39)); `platform/g7x/sub/100b/boot.c`: L161, L321 ([URL](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/platform/g7x/sub/100b/boot.c#L161)) | `loader/g7x/main.c`: L37–39:<br>`    // allows boot on short press without fiddling sub_fc075b56 values or modifying/replacing sub_fc0781f4 (100d addresses)`<br>`    // not clear why not set after DISKBOOT.BIN reboot`<br>`    *(volatile unsigned *)(0x4ffc)=0x12345678;`<br>`platform/g7x/sub/100b/boot.c`: L161:<br>`// no GPIO checks needed with 0x12345678 set, native fw handles long press`<br>L321:<br>`"    bl      sub_fc0781f4\n" // power-on mode handling & startupchecks here, no override needed with 0x12345678 set` | Loader sets DryOS reboot flag `*(0x4ffc) = 0x12345678`; stock power check in `boot.c` is retained unmodified because the reboot flag bypasses shutdown. | **INFERRED** (upstream source inspection) |
| **G7 X Mark II** | GM1.01A | `platform/g7x2/sub/101a/boot.c`: L522, L529–531 ([URL](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/platform/g7x2/sub/101a/boot.c#L522)) | L522: `//            "    beq     loc_e005b49a\n"`<br>L529: `//            "    bl      sub_e004e4d6\n"`<br>L530: `//            "    bl      sub_e004e4d4\n"`<br>L531: `            "    movs    r0, #1\n"` | Replaced callee `sub_e005b418_my`; commented out failure branch; commented out start-cause calls; forced `movs r0, #1`. | **INFERRED** (upstream source inspection) |
| **G3 X (Historical)** | GM1.10E | `g3x_110e.patch` (recovered source: `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:18`, citing patch lines P:1681–1717 at `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:108`) | P:1681, 1697–1703: bypasses `sub_fc079404` and `sub_fc1284ac`<br>P:1685–1691: writes start cause to `*(0x9bc4+0xc)` (`0x80000` power, `0x40000` Wi-Fi, `0x100000` Play)<br>P:1713–1717: `CreateTask("Startup", 0x19, task_Startup_my)` | Bypassed `IsNormalCameraMode` and button check `sub_fc1284ac`; wrote synthesized start cause directly to `*(0x9bc4+0xc)` from button registers before task creation. | **VERIFIED** for recovered patch content (`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:18`, `:108`); applicability to GM1.10C is **UNKNOWN** |

### 2.3 Distinctive Nature of the G3 X Caller Patch
No other DIGIC 6 port verified in the upstream repository supports the caller-side `'bl sub_fc1284ac; movs r0, #1; b loc_fc05b978; nop'` approach directly in the spawner function `sub_fc05b962_my`. Other DIGIC 6 ports modify or replace the callee button-check function (commenting out the branch to shutdown and forcing `movs r0, #1`), simulate a button press inside the callee, rely on the loader setting the DryOS reboot flag `*(0x4ffc) = 0x12345678`, or keep the stock check if the camera firmware already returns 1.

The caller-side approach chosen for G3 X (`movs r0, #1; b loc_fc05b978`) achieves the equivalent effect (guaranteeing that the power-cut call is bypassed and execution continues to task spawning) while preserving the exact 10-byte instruction budget and leaving all downstream offsets untouched. This specific caller-side patch is therefore **INFERRED** for G3 X.

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
- **Ranges:** `PORT24-ROM-NORMAL-MODE` (`0xFC079400`..`0xFC0794BF`, 192 bytes, SHA-256: `cc71c4d4d3014205a860babbed28baa316d475bf1932d2368b5b4cad983a8214`), `PORT24-ROM-NORMAL-FLAG` (`0xFDF20380`..`0xFDF2038F`, 16 bytes, SHA-256: `7998b107f5214f071a101c994a4c8081a9c4abcd72e3970049a923c4bc137f64`)
- **Disassembly:**
  ```arm
  fc079404:	482a      	ldr	r0, [pc, #168]	; (0xfc0794b0)
  fc079406:	7800      	ldrb	r0, [r0, #0]
  fc079408:	b108      	cbz	r0, 0xfc07940e
  fc07940a:	2000      	movs	r0, #0
  fc07940c:	4770      	bx	lr
  fc07940e:	2001      	movs	r0, #1
  fc079410:	4770      	bx	lr
  ```
- **Finding:** At `0xFC0794B0`, literal pool word is `0xFDF20380`. The byte at `0xFDF20380` in ROM is `0x00`, so `sub_fc079404` unconditionally returns `r0 = 1` in stock configuration.

### 5. Startup Reason Recorder `sub_fc08ecbc` (`0xFC08ECBC`) & Structure Pointer `0x9BC4` — `PORT24-ROM-STARTCAUSE-SAVE` & `PORT24-ROM-STARTCAUSE-PTR`
- **Ranges:** `PORT24-ROM-STARTCAUSE-SAVE` (`0xFC08ECB0`..`0xFC08ECFF`, 80 bytes, SHA-256: `039ca184b58d48f853b02fd60a4ad72f45f389790e6da71c6488d99162f8277d`), `PORT24-ROM-STARTCAUSE-PTR` (`0xFC08EEE0`..`0xFC08EEFF`, 32 bytes, SHA-256: `0ceabc1be63a68d5c37a240c220c5e3e4448271ffa11c6d28c4a3d20e72506c6`)
- **Disassembly:**
  ```arm
  fc08ecbc:	b530      	push	{r4, r5, lr}
  fc08ecbe:	4b8c      	ldr	r3, [pc, #560]	; (0xfc08eef0)
  fc08ecc0:	2400      	movs	r4, #0
  fc08ecc2:	9d03      	ldr	r5, [sp, #12]
  fc08ecc4:	60dc      	str	r4, [r3, #12]
  fc08ecc6:	b115      	cbz	r5, 0xfc08ecce
  fc08ecc8:	f44f 3400 	mov.w	r4, #131072	; 0x20000
  fc08eccc:	60dc      	str	r4, [r3, #12]
  fc08ecce:	b112      	cbz	r2, 0xfc08ecd6
  fc08ecd0:	f444 2280 	orr.w	r2, r4, #262144	; 0x40000
  fc08ecd4:	60da      	str	r2, [r3, #12]
  fc08ecd6:	b118      	cbz	r0, 0xfc08ece0
  fc08ecd8:	68d8      	ldr	r0, [r3, #12]
  fc08ecda:	f440 2000 	orr.w	r0, r0, #524288	; 0x80000
  fc08ecde:	60d8      	str	r0, [r3, #12]
  fc08ece0:	2900      	cmp	r1, #0
  fc08ece2:	d003      	beq.n	0xfc08ecec
  fc08ece4:	68d8      	ldr	r0, [r3, #12]
  fc08ece6:	f440 1080 	orr.w	r0, r0, #1048576	; 0x100000
  fc08ecea:	60d8      	str	r0, [r3, #12]
  fc08ecec:	bd30      	pop	{r4, r5, pc}
  ```
- **Literal Value:** At `0xFC08EEF0`, the 32-bit word is `0x00009BC4`. This proves that `0x9BC4` is the start-cause structure on GM1.10C, and `sub_fc08ecbc` writes the startup reason word at offset `+12` (`0x00009BC4 + 12 = 0x00009BD0`): `0x80000` for Power button (`r0`), `0x100000` for Playback button (`r1`), `0x40000` for WiFi button (`r2`), `0x20000` for GPIO 2 (`r5`).

### 6. GPIO Primitives (`0xFC0D73C0`..`0xFC0D73FF`) — `PORT24-ROM-GPIO-PRIMITIVES`
- **Range:** 64 bytes, SHA-256: `00cb15ba364370a85edf8e4c4002f260078fe4e888ab7344d985757c5416c23d`
- **Disassembly:**
  ```arm
  fc0d73c4:	4a07      	ldr	r2, [pc, #28]	; (0xfc0d73e4)
  fc0d73c6:	eb02 0080 	add.w	r0, r2, r0, lsl #2
  fc0d73ca:	f8c0 1800 	str.w	r1, [r0, #2048]	; 0x800
  fc0d73ce:	4770      	bx	lr
  ```
- **Finding:** Literal at `0xFC0D73E4` is `0xD20B0000`. `add.w r0, r2, r0, lsl #2` computes `0xD20B0000 + pin*4`. `str.w r1, [r0, #2048]` adds `0x800` offset (`0xD20B0000 + 0x800 + pin*4 = 0xD20B0800 + pin*4`). For Pin `0x67` (103 decimal): `0xD20B0800 + 103*4 = 0xD20B099C`. Writing `0x004C0003` to `0xD20B099C` controls the PMIC power-hold line.

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
- `boot_witness` address remains `0x0035F7A0` (confirmed by ELF symbol table).
- Core end address (`_end`) remains `0x00366CB0` (confirmed by ELF symbol table).
- Default build produces byte-identical DISKBOOT.BIN SHA-256 `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` (confirmed by build toolchain).

### Analysis of the Start-Cause Risk (**IMPORTANT**)
When the camera is booted via a normal short press, the user's finger has already left the power button by the time `sub_fc1284ac` executes in Stage 5.
As demonstrated by the ROM disassembly above:
1. When all button GPIOs return released, `sub_fc1284ac` branches directly to `0xFC12851A` without calling `sub_fc08ecbc`.
2. Consequently, the start-cause recorder `sub_fc08ecbc` is **not executed**.
3. In `boot_prototype.c:133-153`, `boot()` copies ROM data from `0xFCE91058` into `0x00008000`..`0x0003F4F4` (Copy Loop 3, lines 133–143) and zeroes BSS only at `0x0003F4F4`..`0x003489B4` (lines 144–153). Address `0x9BD0` (`0x9BC4 + 12`) lies within the copied data region (`0x00008000`..`0x0003F4F4`). Because reading new ROM ranges is not permitted in this revision and the ROM source bytes copied to `0x9BD0` are not cited in the evidence manifest, the start-cause word's initial value after `boot()` is **UNKNOWN** (rather than known zero). Without execution of `sub_fc08ecbc`, `0x9BD0` is not updated with `0x00080000` (Power) or `0x00100000` (Play).

#### Comparison with Reference Ports
- **G3 X GM1.10E (ranma)**: As recorded in the recovered source (`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:18` and `:108`, citing patch lines P:1681–1717), ranma bypassed both `IsNormalCameraMode` (`sub_fc079404`) and `sub_fc1284ac` (commented out with TODO "Find out why the default handler in sub_fc1284ac is broken", P:1681, 1697–1703), and wrote the start cause to `*(0x9bc4 + 0xc)` from button-register reads: power `0x80000`, Wi-Fi `0x40000`, otherwise Play `0x100000` (P:1685–1691) before spawning `Startup` (P:1713–1717). That the recovered patch contains this sequence is **VERIFIED** (`docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:18, 108`); whether this 1.10E handling pattern applies to GM1.10C is **UNKNOWN**.
- **G5 X 100C / G7 X Mark II 101A**: As documented in Section 2.2, neither port calls the stock button check directly. Instead, both ports replace the callee (`sub_fc0ecf20_my` in `platform/g5x/sub/100c/boot.c:L411, L418–420`; `sub_e005b418_my` in `platform/g7x2/sub/101a/boot.c:L522, L529–531`), comment out the shutdown failure branch, comment out the start-cause recorder calls, and force `movs r0, #1` before returning, without synthesizing custom start-cause words.
- **Absence of Direct Reference Precedent (**INFERRED**)**: No reference port directly shows the behaviour of keeping the stock G3 X callee `sub_fc1284ac` and forcing `r0 = 1` on the caller side. Instead, reference ports replace the callee entirely (G5 X, G7 X Mark II, SX60 HS), simulate a button press inside the callee (SX710 HS), use a loader reboot flag (G7 X), or retain unmodified firmware checks where stock firmware already returns 1 (M10). The caller-side override in G3 X (`bl sub_fc1284ac; movs r0, #1; b loc_fc05b978; nop`) calls the stock check, which (on short press) skips the start-cause recorder `sub_fc08ecbc`, then overrides `r0 = 1` and skips the power-down branch.
- **Downstream Start-Cause Behaviour**: The downstream start-cause behaviour (the effect of skipping `sub_fc08ecbc`, the initial value copied into `0x9BD0` during `boot()`, and anything else in DryOS that reads the power-on reason `*(0x9BC4 + 12)` later) is **UNKNOWN** (not yet evaluated on physical hardware or via full DryOS decompilation). On physical hardware, the only observed successful boot to the stock user interface (`O1`) was on the unchanged PORT-19 default build (`9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136`) with the physical power button held until the LCD illuminated (which allowed the unmodified second `sub_fc1284ac` call to detect the button). The opt-in candidate (`faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056`) with `movs r0, #1` has **never been run on the camera**. Whether forcing `r0 = 1` and skipping `sub_fc08ecbc` produces any unintended side effects in downstream DryOS tasks remains **UNKNOWN**, while the expectation that it will allow short-press boot without holding the button is **INFERRED** from reference ports and the held-button trial. *(Historical note: The statement that the opt-in candidate has never been run on camera is superseded by the 2026-11-02 trial. In the 2026-11-02 trial, candidate `faad4d8242...` was tested: short press yielded O10 [LCD off, no LED], while held press yielded O1 [stock UI, `CONT_ATTEMPTED / FRESHNESS_UNVERIFIED`]. Removing the check is **VERIFIED insufficient** for a short-press boot [cite 2026-11-02 trial], and the remaining cause is **UNKNOWN**).*

---

## 5. Artifact Verification & Build Hashes

Both builds were executed with the pinned `arm-none-eabi-gcc` toolchain (`gcc-arm-none-eabi-5_4-2016q3`) on the AgentBridge host:

### Default Build (`G3X_POWERON_FIX=0` or undefined)
- Command: `python3 -B tools/build_candidate_port24_poweron_fix.py --default`
- `candidate_main.bin` size: `116,816` bytes
- `candidate_main.bin` SHA-256: `420b3842ed56b59dd0434771694bfd0a5b8e97c9b883d690a2fcad73eb0ffca7`
- `DISKBOOT.BIN` size: `118,001` bytes
- `DISKBOOT.BIN` SHA-256: `9468257364d753d9880791bfce0c0792dd5d0fee29b832566a5eca622a906136` (Matches PORT-19/20/21/23 locked production baseline)
- Symbol `boot_witness`: `0x0035F7A0`
- Symbol `_end`: `0x00366CB0`

### Opt-In Fix Build (`G3X_POWERON_FIX=1`)
- Command: `python3 -B tools/build_candidate_port24_poweron_fix.py --poweron-fix`
- `candidate_main.bin` size: `116,816` bytes
- `candidate_main.bin` SHA-256: `b9c5b718cd90f7a791c216f07f92758cbdfcd56e4e34702235cffdcc204e6580`
- `candidate_main.elf` symbol `boot_witness`: `0x0035F7A0`
- `candidate_main.elf` symbol `_end`: `0x00366CB0`
- `DISKBOOT.BIN` size: `118,001` bytes
- `DISKBOOT.BIN` SHA-256: `faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056`

---

## 6. Claims & Verification Status

| ID | Claim | Evidence / Citation | Status |
|---|---|---|---|
| C0 | Unchanged PORT-19 default build reaches stock UI (`O1`) when physical power button is held until LCD illuminates, but powers off immediately on short press | Recorded owner observation on physical G3 X hardware, 2026-11-01 (`docs/PROJECT_STATE.md`, `docs/HANDOFF.md`) | **VERIFIED** (recorded owner observation) |
| C1 | `sub_fc05b962` at `0xFC05B962` is stock caller of `sub_fc1284ac` and `sub_fc05ba56` | Manifest `PORT24-ROM-CALLER-STARTUP` (`0xFC05B960`..`0xFC05B9BF`, SHA-256 `3403a6bdb72b4895d8a28cba2339318c32536439cd7ee35e06488000ccd8383d`) | **VERIFIED** (direct ROM citation) |
| C2 | `sub_fc05ba56` writes `0x004C0003` to GPIO `0x67`, commanding hardware power-down | Manifest `PORT24-ROM-POWERCUT` (`0xFC05BA50`..`0xFC05BA6F`, SHA-256 `c7b43082682963f5df642e3d16af5971072984845a3bc0a88f31a5f54e76049c`) | **VERIFIED** (direct ROM citation) |
| C3 | `sub_fc1284ac` tests button GPIOs and returns `r0 = 0` when buttons are released | Manifest `PORT24-ROM-POWERON-CHECK` (`0xFC1284A0`..`0xFC12851F`, SHA-256 `f683e2af7e75023d5e311752ab674c1a965933457698a33bf49e78f6a90e4eb0`) | **VERIFIED** (direct ROM citation) |
| C4 | `sub_fc079404` reads camera mode byte from `0xFDF20380` | Manifest `PORT24-ROM-NORMAL-MODE` (`0xFC079400`..`0xFC0794BF`, SHA-256 `cc71c4d4d3014205a860babbed28baa316d475bf1932d2368b5b4cad983a8214`) and `PORT24-ROM-NORMAL-FLAG` (`0xFDF20380`..`0xFDF2038F`, SHA-256 `7998b107f5214f071a101c994a4c8081a9c4abcd72e3970049a923c4bc137f64`) | **VERIFIED** (direct ROM citation) |
| C5 | Startup cause structure is located at RAM `0x00009BC4` | Manifest `PORT24-ROM-STARTCAUSE-SAVE` (`0xFC08ECB0`..`0xFC08ECFF`, SHA-256 `039ca184b58d48f853b02fd60a4ad72f45f389790e6da71c6488d99162f8277d`) and `PORT24-ROM-STARTCAUSE-PTR` (`0xFC08EEE0`..`0xFC08EEFF`, SHA-256 `0ceabc1be63a68d5c37a240c220c5e3e4448271ffa11c6d28c4a3d20e72506c6`) | **VERIFIED** (direct ROM citation) |
| C6 | G5X 100c replaces power handler and removes failure branch | Upstream `01luna/CHDK@21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6`: `platform/g5x/sub/100c/boot.c` L411, L418–420 | **INFERRED** (upstream source code inspection) |
| C7 | SX60HS 100b deletes failure branch `beq.n loc_fc06037e` | Upstream `01luna/CHDK@21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6`: `platform/sx60hs/sub/100b/boot.c` L433, L441–443 | **INFERRED** (upstream source code inspection) |
| C8 | G7X 100b sets `0x4ffc = 0x12345678` for short-press boot | Upstream `01luna/CHDK@21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6`: `loader/g7x/main.c` L37–39; `platform/g7x/sub/100b/boot.c` L161, L321 | **INFERRED** (upstream source code inspection) |
| C9 | Default build DISKBOOT SHA-256 is byte-identical to `9468257364...` | `build_candidate_port24_poweron_fix.py --default` build output | **INFERRED** (local build toolchain result) |
| C10 | Opt-in build DISKBOOT SHA-256 is `faad4d8242fbf6f79a44b10a9956f7eb04de9b65f42221f82a3b69eb024cf056` | `build_candidate_port24_poweron_fix.py` build output | **INFERRED** (local build toolchain result) |
| C11 | Both builds preserve symbol addresses `boot_witness` = `0x0035F7A0` and `_end` = `0x00366CB0` | ELF symbol table disassembly via `arm-none-eabi-nm` | **INFERRED** (ELF inspection) |
| C12 | Failure mechanism: second `sub_fc1284ac` check in `sub_fc05b962_my` cuts power on short press (superseded: removing that check is **VERIFIED insufficient** for a short-press boot [cite 2026-11-02 trial], and the remaining cause is **UNKNOWN**) | GM1.10C ROM disassembly and owner held-button trial observation (and 2026-11-02 owner trial) | **SUPERSEDED** (removing check is **VERIFIED insufficient**; remaining cause is **UNKNOWN**) |
| C13 | Expected opt-in outcome: opt-in candidate power-cut bypass will allow short-press boot to O1 (superseded: short press gave O10 in 2026-11-02 trial, proving bypass is insufficient) | Reasoned from owner held-button trial and DIGIC 6 reference ports (subsequently tested 2026-11-02) | **SUPERSEDED** (removing check is **VERIFIED insufficient** for short press; held press reached O1) |
| C14 | Opt-in candidate (`faad4d8242...`) has reached O1 or been run on physical hardware (superseded: executed in 2026-11-02 owner trial [short press -> O10, held press -> O1]) | STRICT NO-GO in Phase 0; candidate has never been run on camera (pre-trial); 2026-11-02 owner trial | **VERIFIED** (executed in 2026-11-02 owner trial; earlier: **UNKNOWN**) |
| C15 | Downstream start-cause behaviour (`sub_fc08ecbc`, or anything else that reads the power-on reason later) | DryOS task startup decompilation in progress | **UNKNOWN** |
| C16 | In-tree G3 X `boot_prototype.c` contains stock power check calling `sub_fc1284ac` and `sub_fc05ba56` | In-tree git-tracked `chdk-port/platform/g3x/sub/110c/boot_prototype.c` L351–354 (commit `deda42b8ae7c495250d3176a64cd8c3c2146d96f`) | **VERIFIED** (in-tree source code inspection) |

---

## 7. Safety & Scope Rules Compliance

1. **Safety Boundary**: The fix only affects `sub_fc05b962_my` during the second boot stage (post-DISKBOOT entry). It does **not** alter hardware protection, temperature cutoffs, lens barriers, or battery voltage supervision.
2. **Crash Resilience**: If an abnormal condition occurs where power-down was legitimately intended, the camera UI and event procedures (`TurnOffE1_FW`, `task_Startup`) retain full software shutdown capability via normal button event dispatch.
3. **Hardware Policy Compliance**: STRICT NO-GO remains in effect. No binary is flashed, no SD card is written, and no physical camera trial is conducted autonomously. All artifacts are prepared strictly for human owner review and voluntary deployment.
4. **Pre-Existing Test Inconsistency**: In `tests/test_port21_ram_lifetime.py`, entries are filtered for `SCOPE-PORT21-RAM-LIFETIME` because `docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json` already contains merged entries from both `SCOPE-PORT21-RAM-LIFETIME` and `SCOPE-PORT21-DISKBOOT-TIMING` on `origin/main`, which is a pre-existing base inconsistency.

---

## 8. Base Inconsistency in `tests/test_port21_ram_lifetime.py`

When running `python3 -B -m unittest tests.test_port21_ram_lifetime` on the unmodified test from `origin/main`, the test fails on the base tree because `docs/agentbridge/PORT21_EVIDENCE_MANIFEST.json` merges entries from two distinct authorization scopes:
1. `SCOPE-PORT21-RAM-LIFETIME` (6 RAM lifetime ROM ranges approved in PORT-21)
2. `SCOPE-PORT21-DISKBOOT-TIMING` (7 dancing-bits / DISKBOOT timing ranges)

Because the manifest combines more than one authorization scope, the unmodified test (which expects only the 6 entries for `SCOPE-PORT21-RAM-LIFETIME`) raises an `AssertionError` and `KeyError` on the base tree:

```text
======================================================================
ERROR: test_manifest_read_start_notes (tests.test_port21_ram_lifetime.TestPort21EvidenceManifest.test_manifest_read_start_notes)
Each manifest note states its read-start status in the approved wording.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/var/lib/agentbridge/worktrees/g3x-lite/port-24-post-loader-shutdown-p24-poweron-fix-r3/tests/test_port21_ram_lifetime.py", line 616, in test_manifest_read_start_notes
    exception = APPROVED_READS[eid][3]
                ~~~~~~~~~~~~~~^^^^^
KeyError: 'PORT21-ROM-STARTDISKBOOT'

======================================================================
FAIL: test_manifest_matches_approved_reads (tests.test_port21_ram_lifetime.TestPort21EvidenceManifest.test_manifest_matches_approved_reads)
The manifest lists exactly the six approved ranges with their approved SHA-256 values.
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/var/lib/agentbridge/worktrees/g3x-lite/port-24-post-loader-shutdown-p24-poweron-fix-r3/tests/test_port21_ram_lifetime.py", line 602, in test_manifest_matches_approved_reads
    self.assertEqual(set(entries), set(APPROVED_READS))
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: Items in the first set but not the second:
'PORT21-ROM-DANCINGBITS-MAIN'
'PORT21-ROM-EXEC-VALIDATE'
'PORT21-ROM-STARTDISKBOOT'
'PORT21-ROM-PREPARE-EXEC'
'PORT21-ROM-DANCINGBITS-DANCE'
'PORT21-ROM-PAYLOAD-HANDOFF'
'PORT21-ROM-ROW13-TABLE'

======================================================================
FAIL: test_suite_passes_without_rom (tests.test_port21_ram_lifetime.TestPort21WithoutRom.test_suite_passes_without_rom)
----------------------------------------------------------------------
Traceback (most recent call last):
  File "/var/lib/agentbridge/worktrees/g3x-lite/port-24-post-loader-shutdown-p24-poweron-fix-r3/tests/test_port21_ram_lifetime.py", line 1001, in test_suite_passes_without_rom
    self.assertEqual(problems, [], "failures without ROM")
    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
AssertionError: Lists differ: ['tests.test_port21_ram_lifetime.TestPort2[1086 chars]'\n'] != []

First list contains 2 additional elements.
First extra element 0:
'tests.test_port21_ram_lifetime.TestPort21EvidenceManifest.test_manifest_matches_approved_reads: Traceback (most recent call last):\n  File "/var/lib/agentbridge/worktrees/g3x-lite/port-24-post-loader-shutdown-p24-poweron-fix-r3/tests/test_port21_ram_lifetime.py", line 602, in test_manifest_matches_approved_reads\n    self.assertEqual(set(entries), set(APPROVED_READS))\n    ~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^\nAssertionError: Items in the first set but not the second:\n\'PORT21-ROM-DANCINGBITS-MAIN\'\n\'PORT21-ROM-EXEC-VALIDATE\'\n\'PORT21-ROM-STARTDISKBOOT\'\n\'PORT21-ROM-PREPARE-EXEC\'\n\'PORT21-ROM-DANCINGBITS-DANCE\'\n\'PORT21-ROM-PAYLOAD-HANDOFF\'\n\'PORT21-ROM-ROW13-TABLE\'\n'

Diff is 1254 characters long. Set self.maxDiff to None to see it. : failures without ROM

----------------------------------------------------------------------
Ran 28 tests in 0.236s

FAILED (failures=2, errors=1)
```

Per Tech Lead authorization (branch b), `tests/test_port21_ram_lifetime.py` filters manifest entries to `authorization_scope_id == 'SCOPE-PORT21-RAM-LIFETIME'` with a one-line comment and no relaxation of per-entry checks.
