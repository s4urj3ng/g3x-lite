# RESTART-SD-1: SD host and card state across the CHDK-style restart (GM1.10C)

Date: 2026-10-25 · Agent: Claude Code · Offline only.

**Status: `PROTOTYPE_REMEDIATED_OFFLINE / HARDWARE_STRICT_NO_GO`. Isolated prototype fix implemented in `boot_prototype.c` and `stubs_prototype.S`. Candidate port2a and canonical production files remain unaltered.**

ROM: `firmware/dumps/GM1.10C/PRIMARY.BIN` (SHA-256 `99118557…12578`). High RAM `0x010E1000..0x01107D00` ← ROM `0xFCEC854C`; this is recopied by `boot()` and holds the SD driver code. Pinned by `tests/test_restart_sd_audit.py`.

Classification: **V** = verified from ROM bytes · **P** = plausible · **U** = unknown · **X** = contradicts a prior claim.

## 1. What StartDiskboot leaves behind (`0xFC05BBEA`)

1. **Mount (V).** Calls Mounter helpers for drive 0: `0xFC37AE78(0)` at `0xFC05BC12`, then `0xFC37AEA6(0)` at `0xFC05BC18` (its result gates the load), then `0xFC37AED4(0)` at `0xFC05BC26`.
2. **Load (V).** `0xFC05BC3C` → `0xFC05BB98("A/DISKBOOT.BIN")` (falls back to `"A/Upgrader.bin"`): stat, alloc, open `0xFC37B4AE` (`0xFC05BBC2`), read `0xFC37B552` (`0xFC05BBD8`), close `0xFC37B4B0` (`0xFC05BBDE`).
3. **No unmount, no SD power-off on success (V).** The unmount helper `0xFC37AE2A` is called only at `0xFC05BC30`, which is skipped on success because `0xFC05BC7A` branches to `0xFC0D9C9C` and does not return. Its only other caller is `0xFC25664C`. `0xFC0D9C9C` calls IRQ mask, `0xFC41870C` and `0xFC135284`, then jumps through `[0x4000]`.
   - Neither `0xFC41870C` nor the `[0x4000]` target was traced here: **U** whether either touches SD.
4. **Result:** at loader entry, drive A is still mounted. The card is presumably still selected in transfer state and the host still configured. That last part is **P**: the file close does not prove the bus or controller is idle.

## 2. Does repeated DryOS init reset the SD host and card?

- **Driver code and data are restored (V).**
  - `boot()` recopies the High-RAM image containing `SdDrv.c`, `SdPower.c`, `sddom*` and `CMD0_Initialize`.
  - The driver's per-slot table at `0x0026E8B0` (literal `0x010F1B80`, loaded at `0x010F198C`) lies in the BSS that `boot()` zeroes (`0x3F4F4..0x3489B4`).
  - So the software state is fresh (**V**), and the hardware state is not reset by those copies (**V**: copies and zeroing touch RAM only).
- **The SD host is at `0xC8060000` (V).** Register access goes through `0x010F462A` (write) and `0x010F461C` (read): `addr = table[host] + off − 0x38000000`. The table at `0x01107450` is {0, 0x10000, 0x20000}, so host 0 at `0x60000+` maps to `0xC8060000+`.
- **CMD0 exists (V).** `CMD0_Initialize` at `0x010EE7D2` sets command 0 with arg 0 (`0x010F216A`), issues it (`0x010F21AE`), and waits (`0x010F22BA`). Its callers are `0x010E5688` (inside `sddomInitCMD0AndCheckVoltage`) and `0x010EAB1A`.
- **Not proven:**
  - that the continuation (`sub_fc0d0126` → Mounter) actually reaches `sddomInitCMD0AndCheckVoltage` after the restart (**U**). It is plausible given the zeroed driver state (**P**).
  - any host-controller reset (soft-reset bit, FIFO/DMA reset) or SD power cycle (`SdPower.c`) on that path (**U**). I did not enumerate the driver's 244 write call sites.

## 3. Prior claims

| Claim (PORT-2C §2.2 / risk matrix) | Verdict |
|---|---|
| "storage driver re-issues CMD0" | **U.** A CMD0 routine exists; reaching it on the restart path is not proven. |
| "File closed before branch" implies a safe SD state | **X** as a safety argument. Close ≠ unmount; the mount and host state persist (§1.3). |
| Controller FIFO/DMA "must be cleanly re-initialized by the driver" | **U.** No reset write identified. |

## 4. Blocker

Needs one of the following. No fix is justified without it.
1. A static trace from `sub_fc0d0126` through the Mounter into the SD init path, proving CMD0 is issued and identifying any host reset or power-cycle writes at `0xC806xxxx`, together with their order relative to the first command.
2. Approved hardware observation (NO-GO).

Also untraced: `0xFC41870C` and the `[0x4000]` jump target in `0xFC0D9C9C`.

A ROM-backed fix (for example, calling the unmount `0xFC37AE2A(0)` in the loader) is **not** valid. The loader runs after the jump with IRQs masked and with DryOS low RAM overwritten, so DryOS services cannot be called.

## 5. Changes

- New: this doc and `tests/test_restart_sd_audit.py` (ROM byte pins only).
- Executable code, `candidate_port2a/` and production files are unchanged. No SD or camera operations; no commits.

## 6. Addendum (2026-10-25): SD1stInit task registration — DEFINITE OMISSION

**Verified:** `0x010E17A5` is the entry point of task `"SD1stInit"`. It is created only by the stock `StartDiskboot`, which `task_Startup_my` omits.

| Step | Evidence | Kind |
|---|---|---|
| Stock `task_Startup` calls `StartDiskboot` | `0xFC05B90E: bl 0xFC05BBEA` | direct |
| `StartDiskboot` calls the creator veneer, if the code runs from ROM (`0xFC05BBEC..F2`) and `0xFC05C4E0(0)` bit 0 = 0 (`0xFC05BBF6..FC`) | `0xFC05BBFE: blx 0xFC31B1F4` | direct |
| Veneer → creator `0x010E17E0` | `0xFC31B1F4: ldr pc,[pc,#-4]`, literal `0x010E17E1` | direct (veneer) |
| Creator guard: `[0xAC94] == 1` (ROM-data initial value is 1; recopied by `boot()`), then set to 0x81 | `0x010E17E2..EC` | direct |
| `CreateTask("SD1stInit", 0x18, 0, 0x010E17A5, 0)` | `0x010E180C..18`; `0x010F4274` and the kernel CreateTask veneer `0xFC31BBC4` both → `0xBFE14A3D` | direct |
| Task body: if `0x010E1774()` == 1, call `0x010E2A5E(0)` → `0x010E6610` → `0x010E576A` → `0x010E5666` → CMD0 `0x010EE7D2` | `0x010E17A4..BE` | dispatch by scheduler (indirect); calls direct |

- **Only caller:** `0xFC05BBFE` is the sole static caller of `0xFC31B1F4`. No literal or `movw/movt` reference to `0xFC31B1F4` or `0x010E17E1` exists elsewhere.
- **Prototype:** `task_Startup_my` (`boot_prototype.c`) omits `StartDiskboot` and adds no replacement call, so `SD1stInit` is never created on the restart path.
- **Precedent (source comment, not ROM-verified):** the G5X and G7X ports call the equivalent creator before the commented-out `StartDiskboot` ("added for SD card UHS detection", chdk.setepontos.com topic 13089, msg132583).

**Still unverified:**
- whether the other indirect CMD0 entry (`0xFC07564E` → `0x010E1A92`) compensates for the missing task;
- the runtime effect of the omission.

**Fix (implemented in isolated prototype):** call `sub_fc31b1f4` in `task_Startup_my` at the omitted `StartDiskboot` slot, gated by `sub_fc05c4e0(0) & 1 == 0`. See §7 and §8.

## 7. Independent Static Comparison: Stock Startup vs `task_Startup_my`

### 7.1 Control-Flow and Instruction-by-Instruction Comparison

| Sequence / Function | Stock `task_Startup` (`0xFC05B8FC`) | Prototype `task_Startup_my` (Before) | Prototype `task_Startup_my` (Remediated) | Status / Precondition |
|---|---|---|---|---|
| Prologue | `push {r4, lr}` | `push {r4, lr}` | `push {r4, lr}` | Identical |
| Step 1 | `bl 0xFC0D0150` | `bl sub_fc0d0150` | `bl sub_fc0d0150` | Identical |
| Step 2 | `bl 0xFC05BA34` | `bl sub_fc05ba34` | `bl sub_fc05ba34` | Identical |
| Step 3 | `bl 0xFC05BB94` | `bl sub_fc05bb94` | `bl sub_fc05bb94` | Identical |
| Step 4 | `bl 0xFC418EEC` | `bl sub_fc418eec` | `bl sub_fc418eec` | Identical |
| **Step 5 (Diskboot / SD1stInit)** | **`bl 0xFC05BBEA` (`StartDiskboot`)** | **OMITTED** (no replacement) | **Gated call to `sub_fc31b1f4`** | **Remediated** (spawns `SD1stInit` while omitting DISKBOOT load) |
| Step 6 | `bl 0xFC0BBA02` | `bl sub_fc0bba02` | `bl sub_fc0bba02` | Identical |
| Step 7 | `bl 0xFC0D046C` | `bl sub_fc0d046c` | `bl sub_fc0d046c` | Identical |
| Step 8 | `bl 0xFC05BCDC` | `bl sub_fc05bcdc` | `bl sub_fc05bcdc` | Identical |
| Step 9 | `bl 0xFC05BB24` | `bl sub_fc05bb24` | `bl sub_fc05bb24` | Identical |
| Step 10 | `bl 0xFC418F2A` | `bl sub_fc418f2a` | `bl sub_fc418f2a` | Identical |
| Step 11 | `bl 0xFC090674` | `bl sub_fc090674` | `bl sub_fc090674` | Identical |
| Step 12 | `bl 0xFC0D0472` | `bl sub_fc0d0472` | `bl sub_fc0d0472` | Identical |
| Step 13 | `bl 0xFC1283D2` (`task_PhySw`) | `bl sub_fc1283d2` | `bl sub_fc1283d2` | Identical |
| CHDK SpyTask | None (stock) | Commented out | Commented out | Verified inert |
| Step 14..23 | `bl 0xFC2A75F6` .. `0xFC0BB6FE` | 10 matching `bl` calls | 10 matching `bl` calls | Identical |
| Witness Hook | None (stock) | `bl witness_record_continuation` | `bl witness_record_continuation` | Stage 3 recorded |
| Epilogue & Branch | `ldmia sp!, {r4, lr}; b.w 0xFC0D0126` | `pop.w {r4, lr}; b.w sub_fc0d0126` | `pop.w {r4, lr}; b.w sub_fc0d0126` | Identical |

### 7.2 The Original Gate Conditions in Stock StartDiskboot (`0xFC05BBEA`)

Stock `StartDiskboot` executes two gates prior to invoking the `SD1stInit` creator veneer:
1. **Gate 1 (ROM Execution Guard)**:
   ```arm
   fc05bbec: subw r0, pc, #5
   fc05bbf0: lsrs r0, r0, #24
   fc05bbf2: beq.n 0xfc05bc34
   ```
   Checks whether execution is residing in ROM (`PC >> 24 != 0`). In stock ROM cold boot, `PC = 0xFC05BBF4`, `PC >> 24 = 0xFC != 0` (passes). In CHDK, `task_Startup_my` executes from RAM (`0x0034xxxx`), where `PC >> 24 == 0`. Canon implemented this check to prevent RAM-loaded upgrader payloads from recursing into `StartDiskboot`.
2. **Gate 2 (Hardware MMIO Bit Guard & Bit 16 vs Bit 17 Reconciliation)**:
   ```arm
   fc05bbf4: movs r0, #0
   fc05bbf6: bl   0xfc05c4e0
   fc05bbfa: lsls r0, r0, #31
   fc05bbfc: d11a bne.n 0xfc05bc34
   ```
   Calls `0xFC05C4E0(0)` and tests bit 0 of the returned value (`lsls r0, #31; bne exit`).
   
   #### Detailed ROM Disassembly and Hardware MMIO Mapping:
   Subroutine `0xFC05C4E0`:
   ```arm
   fc05c4e0: push    {r4, lr}
   fc05c4e2: movs    r4, #0
   fc05c4e4: cbnz    r0, loc_fc05c4ec
   fc05c4e6: movw    r0, #334            ; 0x14E (property offset for boot mode)
   fc05c4ea: b.n     loc_fc05c4f4
   loc_fc05c4ec:
   fc05c4ec: cmp     r0, #1
   fc05c4ee: bne.n   loc_fc05c4fc        ; Panics/asserts if r0 != 0 and r0 != 1
   fc05c4f0: movw    r0, #335            ; 0x14F (property offset for SD lock)
   loc_fc05c4f4:
   fc05c4f4: bl      sub_fc0d73d0        ; Hardware MMIO reader
   fc05c4f8: mov     r4, r0
   fc05c4fa: b.n     loc_fc05c506
   ...
   fc05c506: mov     r0, r4
   fc05c508: pop     {r4, pc}
   ```
   
   Hardware reader `0xFC0D73D0`:
   ```arm
   fc0d73d0: ldr     r1, [pc, #16]       ; literal at 0xFC0D73E4 -> 0xD20B0000
   fc0d73d2: ldr.w   r0, [r1, r0, lsl #2]; reads MMIO [0xD20B0000 + (r0 << 2)]
   fc0d73d6: lsls    r0, r0, #15         ; Logical shift left by 15, setting flags
   fc0d73d8: bpl.n   loc_fc0d73de        ; Branch if positive / plus (N flag == 0)
   fc0d73da: movs    r0, #1              ; If N flag == 1, return 1
   fc0d73dc: bx      lr
   loc_fc0d73de:
   fc0d73de: movs    r0, #0              ; If N flag == 0, return 0
   fc0d73e0: bx      lr
   ```

   #### Mathematical Proof: Bit 16 (0-indexed) vs "Bit 17" Reconciliation:
   - When called with `r0 = 0`, property index `0x14E` (334) is loaded.
   - Address calculation: `0xD20B0000 + (0x14E << 2) = 0xD20B0000 + 0x538 = 0xD20B0538`.
   - Let 32-bit register `R` contain the MMIO word read from `0xD20B0538`, with bit positions `0..31` (0-indexed, where bit 0 is LSB and bit 31 is MSB).
   - `LSLS R, #15` computes `R' = (R << 15) & 0xFFFFFFFF`.
   - In the ARM architecture, the `N` (Negative) condition flag is set equal to bit 31 (the MSB / sign bit) of the result `R'`.
   - Bit `j` of `R'` receives bit `(j - 15)` of `R`.
   - For bit 31 of `R'`: `31 - 15 = 16`.
   - **Therefore, `N == (R >> 16) & 1`**.
   - If bit 16 of `R` is 0: `N = 0`, `BPL` is taken, returning `r0 = 0`.
   - If bit 16 of `R` is 1: `N = 1`, `BPL` is NOT taken, returning `r0 = 1`.
   - In `StartDiskboot`: `lsls r0, #31; bne exit` aborts if `r0 == 1`. Thus, `SD1stInit` creation proceeds **if and only if bit 16 of MMIO 0xD20B0538 is 0**.
   - **Resolution of "Bit 17" claim**:
     1. In **1-indexed bit numbering** (bits 1 to 32), Bit 0 is the 1st bit, and Bit 16 is the **17th bit**.
     2. Alternatively, calculating `32 - 15 = 17` mistakes the total bit width (32) for the maximum 0-indexed bit position (31), where `31 - 15 = 16`.
     3. The exact hardware bit is proven in ROM: **Bit 16 (0-indexed, bitmask `0x00010000`)**. Tested and verified across all 32 bits by `test_gate_mmio_bit_semantics_reconciliation` in `tests/test_restart_sd_audit.py`.
3. **Creator Call**:
   ```arm
   fc05bbfe: blx  0xfc31b1f4
   ```
   Invokes the ARM veneer at `0xFC31B1F4`, jumping to `0x010E17E1` (High RAM).

### 7.3 Guard Byte Semantics and Duplicate Task Prevention

The High RAM creator routine `0x010E17E0` implements strict, state-machine-backed duplicate task prevention:
1. **Guard Byte `[0x0000AC94]` Check**:
   ```arm
    10e17e0: push  {r3, r4, r5, lr}
    10e17e2: ldr   r4, =0xac94
    10e17e4: ldrb  r0, [r4, #0]
    10e17e6: cmp   r0, #1
    10e17e8: bne.n 0x10e181c          ; Immediate exit if [0xAC94] != 1
   ```
   - On cold boot, Low RAM `0x8000..0x3F4F4` is copied from ROM preimage `0xFCE91058`, initializing `[0x0000AC94] = 1`.
   - When `0x010E17E0` executes:
     - Sets `[0x0000AC94] = 0x81`.
     - Creates event flag at `[0x0000AC98]` (if null) via `0x10F4508`.
     - Calls `CreateTask("SD1stInit", 0x18, 0, 0x010E17A5, 0)` via `0x10F4274`.
   - If called again when `[0x0000AC94] != 1`, it exits immediately via `pop {r3, r4, r5, pc}`, preventing duplicate task creation.
2. **Task Completion and Event Flag Signaling**:
   - `SD1stInit` task body (`0x010E17A4`):
     - Checks `0x010E1774()`. If 1, sets bit 1: `[0x0000AC94] |= 2` (becomes `0x83`) and calls `0x010E2A5E(0)` (CMD0 chain). If not 1, sets bit 2: `[0x0000AC94] |= 4` (becomes `0x85`).
     - Clears bit 0: `[0x0000AC94] &= ~1` (becomes `0x82` or `0x84`).
     - Signals event flag `[0x0000AC98]` via `0x10F4574` to release waiters.
3. **Mounter Synchronization Waiter**:
   - Mounter subsystem at `0xFC37A702` calls veneer `0xFC31BB1C` (`0x010E181E`):
     - Reads `[0x0000AC94]`. If bit 7 (0x80) is set, calls DryOS `WaitEventFlag` on `[0x0000AC98]` with a 10,000 ms (10s) timeout (`0x10E1834`).
     - Clears bit 7: `[0x0000AC94] &= ~0x80`.
   - When `SD1stInit` was omitted, `[0x0000AC94]` stayed `1` (bit 7 clear), so Mounter skipped waiting, but the card was never initialized by `SD1stInit`.
4. **Clean Soft Restart Behavior**:
   - On CHDK restart, `boot()` recopies Low RAM from `0xFCE91058`, resetting `[0x0000AC94]` to `1`.
   - The kernel task table is wiped clean. Spawning `SD1stInit` in `task_Startup_my` registers the task cleanly for the first time in the restarted OS context.

### 7.4 Sister DIGIC 6 Reference Implementations

All sister DIGIC 6 DryOS 57 CHDK ports explicitly replicate this call in place of the omitted `StartDiskboot`:
- **PowerShot G5 X** (`chdk-port/platform/g5x/sub/100c/boot.c` line 450):
  ```c
  // added for SD card UHS detection https://chdk.setepontos.com/index.php?topic=13089.msg132583#msg132583
  "    bl      sub_010e1746\n" // ref in sub_010e1746 following SD1stInit create
  //"    bl      sub_fc0ed356\n" // - startdiskboot
  ```
- **PowerShot G7 X** (`chdk-port/platform/g7x/sub/100d/boot.c` line 352):
  ```c
  // added for SD card UHS detection https://chdk.setepontos.com/index.php?topic=13089.msg132583#msg132583
  "    bl      sub_010e638b\n" // ref in sub_010e647c following SD1stInit create
  //"    bl      sub_fc064b66\n" // StartDiskboot
  ```

---

## 8. Isolated Prototype Implementation & Offline Validation

### 8.1 Implementation in Isolated Prototype

The minimal remediation is applied strictly to isolated prototype files:
1. In `chdk-port/platform/g3x/sub/110c/stubs_prototype.S`:
   - Added `STUB(fc05c4e0)` (Thumb-2 stub for gate check).
   - Added `STUB2(fc31b1f4)` (ARM vector stub for creator veneer).
2. In `chdk-port/platform/g3x/sub/110c/boot_prototype.c` (`task_Startup_my`):
   ```arm
   "    movs    r0, #0\n"
   "    bl      sub_fc05c4e0\n"
   "    lsls    r0, r0, #31\n"
   "    bne     1f\n"
   "    blx     sub_fc31b1f4\n"
   "1:\n"
   ```
3. Canonical production files (`chdk-port/platform/g3x/sub/110c/boot.c`, `chdk-port/loader/g3x/main.c`, `chdk-port/bin/DISKBOOT.BIN`) and candidate artifacts in `candidate_port2a/` remain **100% byte-identical and unaltered**.

### 8.2 Witness Address Stability & Inspector Consistency

- Adding 14 bytes of code and stubs to the prototype shifts `.data` in `prototype_main.elf` by +32 bytes (16-byte aligned):
  - `boot_witness` relocated from `0x0035F780` to `0x0035F7A0` (16-byte aligned, type `D`).
  - Section bounds: `link_data_start = 0x0035AEC0`, `link_bss_start = 0x00365204`, `_end = 0x00366CB0`.
- Validated via dynamic witness inspector tooling:
  - `tools/build_witness_inspector.py` automatically resolves `0x0035F7A0` from `prototype_main.elf` and generates bit-for-bit matching MOVW/MOVT opcodes.
  - `tools/validate_witness_inspector.py` verifies 3-way consistency across ELF, `.bin`, and metadata.
  - `candidate_port2a/` witness address remains pinned at `0x0035F780` and passes candidate validation.

### 8.4 Source Provenance, Patch Artifact & Reproducibility Manifest

1. **Third-Party Upstream Provenance**:
   - `chdk-port` is based on upstream CHDK SVN r5491 (Git commit `21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6` from `https://github.com/01luna/CHDK.git`).
   - Upstream CHDK contains 250+ MB of third-party camera ports and object files, and local build scratch trees containing dumps (e.g. `platform/g5x/sub/100c/PRIMARY.BIN`).
   - To strictly comply with Phase 0 safety rules (never commit proprietary firmware dumps or multi-hundred-MB third-party trees), `chdk-port` is kept as a local build tree with `.gitignore` explicitly scoping tracking.
2. **Tracked Prototype Files**:
   - `.gitignore` explicitly un-ignores and tracks only the clean, non-proprietary G3 X prototype sources:
     - `chdk-port/platform/g3x/sub/110c/boot_prototype.c`
     - `chdk-port/platform/g3x/sub/110c/stubs_prototype.S`
     - `chdk-port/platform/g3x/sub/110c/boot_witness.h`
   - All three files are tracked directly in git on the PR head, eliminating 404 errors and allowing independent review directly in the GitHub PR interface.
3. **Standalone Patch Artifact**:
   - A standalone unified patch is provided at `patches/0001-sd1stinit-restart-prototype.patch`.
   - The patch records upstream provenance, commit SHA `21b9a14eb`, and the clean unified diff for `boot_prototype.c` and `stubs_prototype.S`.
4. **Reproducibility Manifest**:
   - Detailed build manifest, cryptographic artifact hashes, toolchain requirements, and clean-checkout reproduction steps are formally documented in [`docs/REPRODUCIBILITY_MANIFEST.md`](file:///Users/avp/project/g3x-lite/docs/REPRODUCIBILITY_MANIFEST.md).
5. **3-Tier Test Structure & Clean-Checkout Verification**:
   - Tests in `tests/test_restart_sd_audit.py` are explicitly divided into three tiers:
     - **Tier 1 (`TestRestartSdSourcePresence` & `TestRestartSdSkipRegression`)**: Clean checkout source presence, patch validity, static C/ASM syntax checks, MMIO bit arithmetic proof, and skip/fail-closed regression tests. Zero external dependencies; 100% reproducible and passes on any clean git clone without ROM or toolchain (9 / 9 PASS).
     - **Tier 2 (`TestRestartSdRomEvidence`)**: Static ROM disassembly and byte assertions against owner's GM1.10C dump (`PRIMARY.BIN`). Cleanly skipped (`@unittest.skipUnless`) on clean public checkout (7 tests).
     - **Tier 3 (`TestRestartSdOfflineIntegration`)**: Toolchain compilation and ELF symbol resolution for `sub_fc05c4e0` and `sub_fc31b1f4`. Requires `arm-none-eabi-nm`; cleanly skipped when toolchain is absent even if ELF exists (1 test). Fails closed if toolchain is present but prototype build fails.
   - **Test Results by Environment**:
     - *Clean Checkout Simulation (Design Expectation)*: **9 passed, 8 skipped** (zero failures, zero errors across 2 skipped test classes).
     - *Developer Workstation (Actual Verified Run with Full Artifacts)*: **17 passed, 0 skipped**.

### 8.5 Offline Verification Metrics

1. `tests/test_restart_sd_audit.py`: **17 / 17 tests PASS** (0.05s) on developer workstation; **9 passed, 8 skipped** on clean checkout simulation.
   - Verified clean checkout source integrity and patch validity.
   - Verified omission of `sub_fc05bbea` (`StartDiskboot`).
   - Verified inclusion of `sub_fc05c4e0` gate and `blx sub_fc31b1f4`.
   - Verified symbol presence and resolution in `prototype_main.elf`.
   - Verified all 19 ROM byte sequences, 9 ROM words, and strings.
   - Verified regression coverage: missing toolchain cleanly skips Tier 3 without raising `AssertionError`; missing ROM cleanly skips Tier 2; failed compilation fails closed.
2. `tools/validate_prototype_integration.py`: **10 / 10 checks PASS**.
   - Decoupled cache maintenance (`0xFC127AB1` / `0xFC127B09`), core copy, non-overlap, stack boundaries verified.
3. `tools/validate_boot_witness.py`: **12 / 12 checks PASS**.
4. `tools/validate_candidate_port2a.py`: **7 / 7 checks PASS** (Candidate invariance verified via non-mutating validation).
5. `tools/validate_witness_inspector.py`: **13 / 13 checks PASS**.

---

## 9. Remaining Risks and Hardware Caveats

1. **Hardware Execution STRICT NO-GO**: All verifications are strictly static/offline. No code has been deployed or executed on physical camera hardware.
2. **SD Controller State Retention**: While `SD1stInit` re-runs `CMD0_Initialize` (`0x010EE7D2`), the exact hardware state of MMIO host controller `0xC8060000` across soft restart (FIFO state, clock dividers, DMA pointers) remains unobservable without physical telemetry.
3. **Card-Level Response**: Whether all SD cards (especially UHS-I / UHS-II SDXC cards) cleanly accept CMD0 re-issuance from transfer mode (`TRAN`) without a VDD power-cycle drop remains an empirical property of card firmware.
