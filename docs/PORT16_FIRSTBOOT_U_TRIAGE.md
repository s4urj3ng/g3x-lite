# PORT-16 — First-Boot Pipeline Triage of U1–U4 Unknowns (No ROM Reads)

- **Document**: `docs/PORT16_FIRSTBOOT_U_TRIAGE.md`
- **Milestone**: PORT-16 (First-Boot Pipeline Triage)
- **Task ID**: `p16-u-triage-r15`
- **Target Platform**: Canon PowerShot G3 X — Firmware `GM1.10C` (Platform ID `0x32A8` = 12968 dec, DIGIC 6) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:6-7]`. CPU core architecture and core count are `[UNKNOWN]` (tracked statements conflict: `chdk-port/platform/g3x/sub/110c/boot_prototype.c:6` annotates Cortex-A9, whereas `firmware/tools/witness_inspector_payload.S:4` and `docs/PORT11A_GM110C_ROM_EVIDENCE.md:20` annotate Cortex-R4; `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:82` documents this contradiction; zero CPU-mode inference is made).
- **Safety Gate**: **`STRICT NO-GO FOR HARDWARE DEPLOYMENT`** (Phase 0 read-only offline investigation; zero hardware trials, zero binary modifications, zero new ROM dumps, zero ROM bytes read or quoted) `[VERIFIED: docs/SAFETY.md:1-8]`.
- **Evidence Policy**: Every claim in this document carries an explicit `[VERIFIED]`, `[INFERRED]`, or `[UNKNOWN]` label and cites only Git-tracked repository files `[VERIFIED]`. No untracked files are cited as evidence, no ROM bytes, opcode words, or instruction encodings are read or quoted, and no addresses are inferred without a cited tracked source `[VERIFIED]`.

> **Scope Note**:  
> This document triages the U1–U4 unknown runtime obligations for the first-boot pipeline of Canon PowerShot G3 X GM1.10C under the narrow first-boot definition: first boot means only that `DISKBOOT.BIN` loads, the corrected boot stub in `chdk-port/platform/g3x/sub/110c/` runs, and the boot witness becomes observable to the owner through the witness inspector. It does NOT include filesystem flush or unmount integrity, lock ownership or task-priority behaviour, unless a cited line of the boot stub, the build or the inspector actually depends on them. In accordance with Phase 0 safety protocol, zero ROM bytes are read, zero binary payloads are built or modified, and zero physical camera operations are performed; all evidence is derived from tracked repository sources `[VERIFIED: docs/SAFETY.md:1-8]`.

## First-Boot Triage Summary Table

| Item | Decision | Label | Citation | ROM Ranges |
|---|:---:|:---:|---|:---:|
| **U1** | **`NOT_NEEDED_FOR_FIRST_BOOT`** | `[VERIFIED]` | `chdk-port/platform/g3x/sub/110c/boot_prototype.c:358-366` (veneer at `:365`); `tools/port9b_runtime_contract.py:453` | None (0 B) |
| **U2(a)** | **`NOT_NEEDED_FOR_FIRST_BOOT`** | `[VERIFIED]` | `tools/port9b_runtime_contract.py:455-456`; `chdk-port/platform/g3x/sub/110c/boot_prototype.c:377-436`; `docs/PORT13_OBLIG_U4.md:70`; `docs/PORT11A_GM110C_ROM_EVIDENCE.md:239, 407` | None (0 B) |
| **U2(b)** | **`NOT_NEEDED_FOR_FIRST_BOOT`** | `[VERIFIED: source; INFERRED: path]` | `chdk-port/platform/g3x/sub/110c/boot_prototype.c:27-29, 39, 52, 411-416`; `tools/port9b_runtime_contract.py:455-456`; `tools/port13_u2_obligations.py:680-730` | None (0 B) |
| **U2(c)** | **`NEEDED_FOR_FIRST_BOOT`** | `[UNKNOWN]` | `firmware/tools/witness_inspector_gm110c.m:100-121`; `tools/port13_u2_obligations.py:782-806` (`OBLIG-U2-08`) | None (0 B) *(not ROM-closable)* |
| **U2(d)-stock** | **`NEEDED_FOR_FIRST_BOOT`** | `[UNKNOWN]` | `tools/port13_u2_obligations.py:628-678` (`OBLIG-U2-02`, `OBLIG-U2-03`); `firmware/tools/witness_inspector_gm110c.m:100-121` | None (0 B) *(not ROM-closable)* |
| **U2(d)-CHDK** | **`NOT_NEEDED_FOR_FIRST_BOOT`** | `[VERIFIED: source; INFERRED: path]` | `docs/PORT10A_RUNTIME_PRECONDITION_EVIDENCE.md:180-183`; `chdk-port/platform/g3x/sub/110c/boot_prototype.c:411-416` | None (0 B) |
| **U3** | **`NOT_NEEDED_FOR_FIRST_BOOT`** | `[INFERRED]` | `chdk-port/platform/g3x/sub/110c/boot_prototype.c:409`; `tools/port9b_runtime_contract.py:454`; `firmware/tools/witness_inspector_gm110c.m:52, 62, 185-188` | None (0 B) |
| **U4(a)** | **`NOT_NEEDED_FOR_FIRST_BOOT`** | `[VERIFIED]` | `chdk-port/platform/g3x/sub/110c/boot_prototype.c:411-416`; `tests/test_port9b_runtime_contract.py:86-89`; `tools/port13_oblig_u4.py:168-294, 310-325` | None (0 B) |
| **U4(b)(i)** | **`NOT_NEEDED_FOR_FIRST_BOOT`** | `[VERIFIED: source; INFERRED: path]` | `chdk-port/platform/g3x/sub/110c/boot_prototype.c:358-366, 411-416`; `tools/port9b_runtime_contract.py:457`; `tools/port13_oblig_u4.py:199-215` (`OBLIG-U4-03`) | None (0 B) |
| **U4(b)(ii)** | **`NEEDED_FOR_FIRST_BOOT`** | `[UNKNOWN]` | `chdk-port/platform/g3x/sub/110c/boot_prototype.c:434`; `tools/port13_oblig_u4.py:295-309` (`OBLIG-U4-09`) | None (0 B) *(not ROM-closable)* |
| **U4(c)** | **`NEEDED_FOR_FIRST_BOOT`** | `[UNKNOWN]` | `tools/port13_oblig_u4.py:326-341` (`OBLIG-U4-11`); `docs/RESTART_SD_HOST_AUDIT.md:11-29`; `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:80-82` | None (0 B) *(not ROM-closable)* |
| **Witness Addr** | **`NEEDED_FOR_FIRST_BOOT`** | `[VERIFIED: host binding; UNKNOWN: camera readout]` | `tools/build_candidate_port2a.py:651-701, 830-833`; `docs/PORT16_CANDIDATE_BUILD.md:26`; `firmware/tools/witness_inspector_payload.S:57-93` | None (0 B) *(not ROM-closable)* |
| **Dual Markers** | **`NEEDED_FOR_FIRST_BOOT`** | `[UNKNOWN]` | `docs/HANDOFF.md:435, 463`; `docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:20-25` | None (0 B) *(not ROM-closable)* |
| **Witness Freshness** | **`NEEDED_FOR_FIRST_BOOT`** | `[UNKNOWN]` | `tools/build_candidate_port2a.py:783`; `firmware/tools/witness_inspector_payload.S:96-113, 165-174`; `firmware/tools/witness_inspector_gm110c.m:28`; `docs/HANDOFF.md:430, 466` | None (0 B) *(not ROM-closable)* |
| **Mode Transition** | **`NEEDED_FOR_FIRST_BOOT`** | `[UNKNOWN]` | `firmware/tools/witness_inspector_gm110c.m:185-188`; `docs/HANDOFF.md:1439` | None (0 B) *(not ROM-closable)* |

---

## 1. Canonical Definition of First Boot

The scope of this triage is strictly governed by the canonical first-boot definition `[VERIFIED]`:

> **Canonical Definition of First Boot**:  
> *First boot means only this: DISKBOOT.BIN loads, the corrected boot stub in `chdk-port/platform/g3x/sub/110c/` runs, and the boot witness becomes observable to the owner through the witness inspector. It does NOT include filesystem flush or unmount integrity, lock ownership or task-priority behaviour, unless a cited line of the boot stub, the build or the inspector actually depends on them. Nothing beyond that counts.* `[VERIFIED]`

### 1.1 Architectural Stages of the First-Boot Execution Path

Under this canonical definition, the complete execution sequence comprises strictly three sequential phases and nothing beyond them `[INFERRED]`:

1. **Phase A: DISKBOOT.BIN Loading** `[INFERRED: standard Canon bootloader mechanism]`:
   - Stock Canon firmware bootloader (`StartDiskboot` at `0xFC05BBEA` in ROM `[VERIFIED: docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:229; chdk-port/platform/g3x/sub/110c/boot_prototype.c:374]`) evaluates the boot markers in the SD card VBR: `BOOTDISK` at offset `0x1E0` for loading `DISKBOOT.BIN` (`docs/HANDOFF.md:435, 463; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:33`), and `SCRIPT` at offset `0x1F0` for Canon Basic script activation (`docs/HANDOFF.md:435, 463; docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:20-25`) `[VERIFIED: docs/HANDOFF.md:435, 463; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:33; docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:20-25]` (whether FAT16 requires a distinct `BOOTDISK` offset is `[UNKNOWN]` and no alternate offset is inferred). Specifically, `BOOTDISK` serves the purpose of loading the candidate binary (`DISKBOOT.BIN`), while `SCRIPT` serves the purpose of running the witness inspector script (`firmware/tools/witness_inspector_gm110c.m`) `[VERIFIED: docs/HANDOFF.md:435, 463]`. (No marker is called `'DISKBOOT'` `[VERIFIED: docs/HANDOFF.md:435; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:33]`). When `BOOTDISK` is detected, the bootloader reads `DISKBOOT.BIN` from the FAT filesystem, relocates the payload to DRAM, and branches to the loader entry point `[INFERRED: docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:101-111; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:229]`.
   - The CHDK loader relocates the core binary to `MEMISOSTART = 0x003489B4` and jumps to the relocated core entry point `boot()` at `0x003489B4` (`0x003489B5` Thumb interworking) as defined in source behavior `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:40, 82-85; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:21, 126; docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:101-102]`. Dynamic runtime execution of this relocation and handoff on physical hardware is `[INFERRED]` and empirically `[UNKNOWN]`.

2. **Phase B: Corrected Boot Stub Execution (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:85-436`)** `[VERIFIED: source behavior]`:
   - **Stage 1 (`boot()`, `chdk-port/platform/g3x/sub/110c/boot_prototype.c:85-158`)** `[VERIFIED: source behavior]`:
     - Resets initial stack pointer to `sp = 0x4000` via lines 89-91 (`"    movw    r0, #0x4000\n" ... "    mov     sp, r0\n"`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:89-91]`.
     - Copies exception vector table (`0xFC05B47C..0xFC05B4B4` $\to$ `0x00000000`) via `bl sub_fc02007e` at line 98 (`"    bl      sub_fc02007e\n"`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:98]`.
     - Enables peripheral bus clock gate (`*(uint32_t*)0xC0242010 |= 1`) at lines 101-104 (`"    ldr     r2, =0xc0242010\n"`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:101-104]`.
     - Copy Loop 1: Copies High RAM (`0x010E1000..0x01107D00`) from ROM `0xFCEC854C` at lines 106-115 (`"    ldr     r0, =0xfcec854c\n"`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:106-115]`.
     - Cleans full L1 data cache via `bl sub_fc127a62` (`0x010E1000`, size `0x26D00 >= 0x4000`) at lines 118-120 (`"    bl      sub_fc127a62\n"`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:118-120; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:106, 300]`.
     - Copy Loop 2: Copies ATCM (`0xBFE10800..0xBFE17419`) from ROM `0xFCEEF24C` at lines 122-131 (`"    ldr     r0, =0xfceef24c\n"`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:122-131]`.
     - Copy Loop 3: Copies Low RAM (`0x00008000..0x0003F4F4`) from ROM `0xFCE91058` at lines 133-142 (`"    ldr     r0, =0xfce91058\n"`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:133-142]`.
     - Zeroes Canon BSS (`0x0003F4F4..0x003489B4`), terminating strictly at `0x003489B4` (`MEMISOSTART`), preserving relocated CHDK core in DRAM, at lines 144-153 (`"    ldr     r1, =0x003489b4\n"`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:144-153]`.
     - Branches to heap reservation trampoline `b.w sub_fc05b3c8_my` at line 156 `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:156]`.
   - **Stage 2 (`sub_fc05b3c8_my()`, `chdk-port/platform/g3x/sub/110c/boot_prototype.c:164-258`)** `[VERIFIED: source behavior]`:
     - Records Stage 2 in boot witness: calls `witness_record_core()` at line 170 (`"    bl      witness_record_core\n"`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:170]`.
     - Dynamically loads shifted heap boundary `r4 = new_sa` (`&_end`) at lines 173-174 (`"    ldr     r4, =new_sa\n"`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:173-174]`.
     - Allocates 120-byte (`0x78`) setup structure on stack at line 177 `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:177]`.
     - Verifies DRAM headroom (`0x006CE000 - r4 >= 0x000B1FEC` = 712 KiB) at lines 180-184 `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:180-184]`.
     - Configures Low RAM system registers (`0x8074`, `0x8078`, `0x807C`) at lines 189-198 `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:189-198]`.
     - Clears the 120-byte setup structure via `memset(sp, 0, 0x78)` via `sub_fc31bfac` at lines 201-203 `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:201-203]`.
     - Populates DryOS kernel memory descriptors with shifted heap base `sp[0x08] = new_sa` at lines 206-213 `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:206-213]`.
     - Configures DryOS OS entity limits (`sp[0x18] = 0x22` tasks, `sp[0x1C] = 0xCA` semaphores, `sp[0x20] = 0x2B0` msg queues, `sp[0x5C] = 0x10` prios, `sp[0x60] = 0x1000` stack, etc.) at lines 215-237 `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:215-237]`.
     - Initializes calling convention for initial task continuation: `sp[0x38]` is cleared to 0 at lines 231-232 (`"    movs    r0, #0\n" ... "    str     r0, [sp, #0x38]\n"`), the hooked continuation entry point `sub_fc05b558_my` is loaded into register `r1` at line 240 (`"    ldr     r1, =sub_fc05b558_my\n"`), and `r0 = sp` points to the setup structure at line 251 (`"    mov     r0, sp\n"`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:231-232, 240, 251]`.
     - Dispatches into stock DryOS kernel initialization `blx sub_fc31b408` with `(r0=sp, r1=sub_fc05b558_my)` at line 252 `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:252]`.
   - **Stage 3 (`sub_fc05b558_my()`, `chdk-port/platform/g3x/sub/110c/boot_prototype.c:264-332`)** `[VERIFIED: source behavior]`:
     - Initializes debug manager, terminal driver, stdio, stdlib, and extlib via stock ROM calls at lines 267-326 `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:267-326]`.
     - Branches to hooked startup task spawner `b.w sub_fc05b962_my` at line 330 `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:330]`.
   - **Stage 4 (`sub_fc05b962_my()`, `chdk-port/platform/g3x/sub/110c/boot_prototype.c:338-370`)** `[VERIFIED: source behavior]`:
     - Invokes stock hardware power checks (`sub_fc1284ac`) at line 346 `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:346]`.
     - Spawns hooked `task_Startup_my` via stock DryOS `CreateTask` veneer `blx sub_fc31bbc4` (name `"Startup"`, prio `0x19`, default stack) at lines 358-366 (veneer call at line 365: `"    blx     sub_fc31bbc4\n"`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:358-366]`.
   - **Stage 5 (`task_Startup_my()`, `chdk-port/platform/g3x/sub/110c/boot_prototype.c:377-436`)** `[VERIFIED: source behavior]`:
     - Executes early stock Canon driver setup subroutines (`sub_fc0d0150`, `sub_fc05ba34`, `sub_fc05bb94`, `sub_fc418eec`) at lines 381-384 `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:381-384]`.
     - Replicates `StartDiskboot` gate (`sub_fc05c4e0(0) & 1 == 0`) and spawns `SD1stInit` via stock veneer `blx sub_fc31b1f4` at lines 386-398 (veneer call at line 397: `"    blx     sub_fc31b1f4\n"`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:386-398]`.
     - Calls subsequent stock setup subroutines (`sub_fc0bba02`, `sub_fc0d046c`, etc.) at lines 400-406 `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:400-406]`.
     - Launches unmodified stock `task_PhySw` via `bl sub_fc1283d2` at line 409 (`"    bl      sub_fc1283d2\n"`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:409]`.
     - **CHDK SpyTask is completely commented out and disabled**: lines 411-416 (commented call at line 416 is `// "    bl      CreateTask_spytask\n"`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:411-416]`.
     - Completes remaining Canon startup subroutines (`sub_fc2a75f6` .. `sub_fc0bb6fe`) at lines 418-427 `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:418-427]`.
     - Records Stage 3 in boot witness: calls `witness_record_continuation()` at line 430 (`"    bl      witness_record_continuation\n"`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:430]`.
     - Resumes stock Canon firmware continuation via terminal branch `b.w sub_fc0d0126` at line 434 (`"    b.w     sub_fc0d0126\n"`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:434]`.

3. **Phase C: Boot Witness Observability Path** `[INFERRED: established hardware observation path]`:
   - Following the continuation branch `b.w sub_fc0d0126` (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:434`), stock Canon firmware startup completes and the camera enters **Playback mode** (as initiated by the owner booting the camera via Playback button press) `[INFERRED: operational boot procedure]`.
   - The owner launches the non-blocking Canon Basic witness inspector script `firmware/tools/witness_inspector_gm110c.m` in Playback mode `[INFERRED: operational procedure]`.
   - In `firmware/tools/witness_inspector_gm110c.m`, the inspector creates message descriptors via `LCDMsg_Create` at lines 52 and 62 (`h_title = LCDMsg_Create()`, `h_status = LCDMsg_Create()`) `[VERIFIED: firmware/tools/witness_inspector_gm110c.m:52, 62]`.
   - The script opens and reads the compiled inspector payload binary from the SD card using `fh = Fopen_Fut("A/WITNESS.BIN", "rb")` at line 100, `read_sz = Fread_Fut(buf, 1, payload_size + 1, fh)` at line 109, and `cl = Fclose_Fut(fh)` at line 110 `[VERIFIED: firmware/tools/witness_inspector_gm110c.m:100, 109, 110]`. If any of these file operations fails (`fh = 0`, `read_sz <> payload_size`, `cl <> 0`), the script immediately aborts via `exit sub` at lines 105, 115, and 121 before executing the payload `[VERIFIED: firmware/tools/witness_inspector_gm110c.m:101-121]`.
   - The script cleans and invalidates Harvard caches at lines 127-128 and dispatches the native payload via `ret_val = ExecuteEventProcedure("exec", buf + 1, h_title, h_status, expected_nonce, 0, 0)` at line 136 `[VERIFIED: firmware/tools/witness_inspector_gm110c.m:127-136]`.
   - **Witness-Address Host-Side Binding Completed and Verified**: The host-side binding of the witness inspector to `0x0035F7A0` is completed and verified `[VERIFIED: tools/build_candidate_port2a.py:651-701, 830-833; docs/PORT16_CANDIDATE_BUILD.md:26]`. The candidate builder `tools/build_candidate_port2a.py:651-701, 830-833` generates and checks the aligned inspector payload (`candidate_port2a/witness_inspector_payload.bin`) and metadata (`candidate_port2a/witness_inspector_metadata.json`) targeted to `boot_witness` at `0x0035F7A0` exclusively inside the build output directory `candidate_port2a/`, without modifying historical artifacts under `firmware/tools/` (`docs/PORT16_CANDIDATE_BUILD.md:26`). Only the physical observation on the camera remains `[UNKNOWN]`, and it is closed by the owner trial when the camera executes the aligned inspector payload and renders the witness state without `ERR_READ` or corrupted witness data (`firmware/tools/witness_inspector_payload.S:57-93`).
   - **Inspector Script Descriptor Handling in RAM (Source Behavior)**: In tracked code, the inspector script finishes with a non-blocking exit (`zero polling, zero Wait()`), and message descriptors are intentionally retained in firmware RAM for Live View inspection in Shooting mode (`firmware/tools/witness_inspector_gm110c.m:185-188`) `[VERIFIED: firmware/tools/witness_inspector_gm110c.m:185-188]`.
   - **Recorded Historical Observation Sequence**: In tracked hardware trial records, the recorded operational sequence was Playback boot $\to$ `FUNC./SET` pressed once $\to$ owner half-pressed shutter after ~1–2s $\to$ smooth transition to Shooting mode Live View without display freeze $\to$ telemetry lines appeared simultaneously and clearly on LCD (`docs/HANDOFF.md:1439`) `[VERIFIED: docs/HANDOFF.md:1439]`.
   - **Internal Playback Mode Display Behavior**: The internal firmware mechanism and claim regarding why `LCDMsg` descriptors do not render interactively during Playback script execution cannot be verified from tracked files because the review document (`docs/UI001C_DESIGN_REVIEW.md`) is untracked at BASE and is classified as `[UNKNOWN]` (see Section 1.2) `[UNKNOWN]`.
   - **Historical BOOT-001A Trial Result Details**: The primary execution report for `BOOT-001A` is untracked at BASE (`docs/BOOT001A_HARDWARE_RESULT.md`), so specific findings resting exclusively on it are classified as `[UNKNOWN]` from tracked records (see Section 1.2) `[UNKNOWN]`. Tracked `docs/HANDOFF.md:434, 1439` documents the hardware-verified readout pathway and the Playback-to-Shooting mode transition sequence for `UI-001B-0`.
   - **Expected Operational Behavior for Corrected Candidate Build**: For THIS candidate build, message descriptors are expected to stay in RAM after the non-blocking script finishes in Playback mode, and then render on the LCD screen after the owner switches the camera from Playback mode to Shooting Live View (e.g. by pressing the shutter button) `[INFERRED: expected operational behavior for this build based on firmware/tools/witness_inspector_gm110c.m:185-188 and docs/HANDOFF.md:1439]`.
   - **Current Inspector Payload Rendering Logic (Source Behavior)** `[VERIFIED: firmware/tools/witness_inspector_payload.S:16-21, 165-174, 250-258]`:
     - In tracked source code, the current inspector payload formats Title line `"CONT_ATTEMPTED"` (`firmware/tools/witness_inspector_payload.S:250-251`) `[VERIFIED: firmware/tools/witness_inspector_payload.S:250-251]`.
     - In tracked source code, the current inspector payload formats Status line `"FRESHNESS_UNVERIFIED"` in Yellow / Color 4 (`firmware/tools/witness_inspector_payload.S:172-174, 257-258`) `[VERIFIED: firmware/tools/witness_inspector_payload.S:172-174, 257-258]`.
     - In tracked source code, per `firmware/tools/witness_inspector_payload.S:16-21`, the inspector deliberately enforces that a matching constant nonce is never considered freshness proof, every complete record lacking an independently verified current-attempt challenge is visibly labeled `FRESHNESS_UNVERIFIED`, misleading green success coloring is strictly prohibited, and the inspector deliberately never reports `BOOT_SUCCESS` or `CONTINUATION_CONFIRMED` (`firmware/tools/witness_inspector_payload.S:16-21, 165-174; tools/validate_witness_inspector.py:4-20, 89-108`) `[VERIFIED: firmware/tools/witness_inspector_payload.S:16-21, 165-174; tools/validate_witness_inspector.py:4-20, 89-108]`.
   - **Actual Current Attempt Display and Witness Freshness** `[UNKNOWN]`:
     - What the current inspector will actually show on physical hardware for the current attempt remains empirically unverified `[UNKNOWN]`.
     - Whether the witness recorded in DRAM is genuinely fresh (written by the candidate in the current boot generation) or stale memory residue from a prior boot remains unproven `[UNKNOWN: firmware/tools/witness_inspector_gm110c.m:28; firmware/tools/witness_inspector_payload.S:165-174; docs/HANDOFF.md:430, 466; docs/PORT3C_RESTART_READINESS_MATRIX.md:22-25; docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:66]`.
   - **Qualified First-Boot Observation Criterion** `[INFERRED]`:
     - First boot counts as observed only with evidence that the corrected stub ran in the CURRENT attempt, i.e. a fresh witness written by this candidate, not stale RAM or a historical banner `[INFERRED]`.
     - The outcome of the owner's future physical trial on target hardware remains empirically undetermined `[UNKNOWN]`.

### 1.2 Unavailable Citations

The following three documents are local git-ignored files and are not tracked at BASE or HEAD `[VERIFIED]`:
1. `docs/UI001C_DESIGN_REVIEW.md`: Not tracked in git history `[VERIFIED]`.
2. `docs/BOOT001A_HARDWARE_RESULT.md`: Not tracked in git history `[VERIFIED]`.
3. `docs/CHDK_PORT1F2_FINAL_EVIDENCE.md`: Not tracked in git history `[VERIFIED]`.

Per repository policy and review directive, untracked files are strictly not cited as evidence, and their content is not quoted as evidence `[VERIFIED]`. All proposed owner-trial procedures are labeled `[INFERRED]` and designated as proposed observations for the owner trial plan `[VERIFIED]`. Claims resting exclusively on untracked historical review notes are classified as `[UNKNOWN]` `[VERIFIED]`:
- **Interactive Playback LCDMsg Compositing**: The internal firmware mechanism and claim regarding why `LCDMsg` descriptors do not render interactively during Playback script execution (previously attributed to `docs/UI001C_DESIGN_REVIEW.md`) is `[UNKNOWN]` from tracked records. Tracked source code (`firmware/tools/witness_inspector_gm110c.m:185-188`) documents only that message descriptors are retained in RAM for Live View inspection in Shooting mode, and tracked trial records (`docs/HANDOFF.md:1439`) document the operational sequence of transitioning to Shooting Live View to observe displayed lines.
- **Historical BOOT-001A Execution Details**: The primary execution report and on-screen banner observation of `BOOT-001A` (previously attributed to `docs/BOOT001A_HARDWARE_RESULT.md`) is `[UNKNOWN]` from tracked records. Tracked `docs/HANDOFF.md:434, 1439` documents the hardware-verified readout pathway and the Playback-to-Shooting mode transition sequence for `UI-001B-0`.
- **CHDK-PORT-1F.2 Evidence Bundle Details**: The specific review document text and local analysis bundle for dual-flag boot marker evaluation, hardware coexistence, and warm-reboot DRAM retention (previously attributed to `docs/CHDK_PORT1F2_FINAL_EVIDENCE.md`) is `[UNKNOWN]` from tracked records. The underlying facts are supported by tracked files `docs/HANDOFF.md:430-466`, `docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:33, 229`, `docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:20-25`, `docs/PORT3C_RESTART_READINESS_MATRIX.md:22-25`, and `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:66`.

---

## 2. Comprehensive Triage Matrix

| Item | Scope / Obligation Citation | First-Boot Decision | Epistemic Label | Reason / File:Line Citation | ROM Ranges |
|---|---|:---:|:---:|---|:---:|
| **U1** | `CreateTask` prologue bytes and replayed literal (`docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:140; tools/port13_oblig_u4.py:184-198`, `OBLIG-U4-02`) | **`NOT_NEEDED_FOR_FIRST_BOOT`** | `[VERIFIED]` | Prototype invokes stock `CreateTask` veneer directly (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:358-366`, veneer at line 365); no task interception installed (`tools/port9b_runtime_contract.py:453`). | **None (0 B)** |
| **U2(a)** | CHDK `InitFileModules` gate, replacement task and CHDK readiness latch (`docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:141`; `OBLIG-U2-06`, `OBLIG-U2-07` at `tools/port13_u2_obligations.py:732-779`) | **`NOT_NEEDED_FOR_FIRST_BOOT`** | `[VERIFIED]` | CHDK core performs zero file access during first boot; `InitFileModules` hook and gate absent in source (`tools/port9b_runtime_contract.py:455-456; chdk-port/platform/g3x/sub/110c/boot_prototype.c:377-436; docs/PORT13_OBLIG_U4.md:70; docs/PORT11A_GM110C_ROM_EVIDENCE.md:239, 407`). | **None (0 B)** |
| **U2(b)** | Deferred CHDK filesystem assertions & mount state preconditions (`tools/port13_u2_obligations.py:680-730`, `OBLIG-U2-04`, `OBLIG-U2-05`) | **`NOT_NEEDED_FOR_FIRST_BOOT`** | `[VERIFIED: source; INFERRED: path]` | First boot writes `boot_witness` directly to DRAM (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:27-29, 39, 52`); CHDK SpyTask disabled (`:411-416`); no CHDK file operations or mount assertions evaluated (`tools/port9b_runtime_contract.py:455-456; tools/port13_u2_obligations.py:680-730`). | **None (0 B)** |
| **U2(c)** | Stock SD read capability & warm-restart SD re-enumeration without bus lockup (`firmware/tools/witness_inspector_gm110c.m:100-121`; `tools/port13_u2_obligations.py:782-806`, `OBLIG-U2-08`) | **`NEEDED_FOR_FIRST_BOOT`** | `[UNKNOWN]` | Inspector aborts via `exit sub` before inspecting if open, read, or close fails (`firmware/tools/witness_inspector_gm110c.m:100-121`). `OBLIG-U2-08` covers SD re-enumeration without bus lockup (`tools/port13_u2_obligations.py:782-806`). The dependency of these reads on stock `task_InitFileModules` dispatch/completion is triaged separately under U2(d)-stock. Not ROM-closable: dynamic runtime driver/controller execution across warm restart (`kind=ObligationKind.RUNTIME`, `status=ObligationStatus.UNKNOWN`, `tools/port13_u2_obligations.py:788-789`). Closed when inspector file open, read and close succeed in current attempt. | **None (0 B)** *(not ROM-closable)* |
| **U2(d)-stock** | Stock `task_InitFileModules` scheduler dispatch in the current boot generation (`OBLIG-U2-02`, `tools/port13_u2_obligations.py:628-649`) and normal return of stock `sub_fc0d9ccc` / `sub_fc0d9cf6` in the current boot generation (`OBLIG-U2-03`, `tools/port13_u2_obligations.py:652-678`) | **`NEEDED_FOR_FIRST_BOOT`** | `[UNKNOWN]` | Whether the inspector's stock file reads (`firmware/tools/witness_inspector_gm110c.m:100-121`) depend on stock `task_InitFileModules` dispatch and normal completion cannot be shown from the cited source; no cited line of the boot stub, the build or the inspector shows that first boot does not depend on it, so it is not deferred. Not ROM-closable: both obligations are `kind=ObligationKind.RUNTIME` and state that static ROM entry evidence cannot discharge them (`tools/port13_u2_obligations.py:634-635, 648, 659-660, 676`). Closure split: (a) Functional first-boot observation: in the same attempt, all three inspector file operations (open, read, and close) succeed; reaching the stock UI alone does not establish this because the inspector can abort on any failure (`firmware/tools/witness_inspector_gm110c.m:100-121`); (b) Canonical obligation discharge: requires current-generation execution evidence for `task_InitFileModules` and completion evidence for `sub_fc0d9ccc` / `sub_fc0d9cf6` (`tools/port13_u2_obligations.py:628-678`). Observation (a) does not discharge (b); `OBLIG-U2-02/03` stay `UNKNOWN` after a successful first boot unless (b) is observed. | **None (0 B)** *(not ROM-closable)* |
| **U2(d)-CHDK** | CHDK-side SpyTask-driven consumption of `InitFileModules` completion: upstream `core_spytask` clears and waits up to 10 s on `spytask_can_start`, then continues on timeout (`docs/PORT10A_RUNTIME_PRECONDITION_EVIDENCE.md:180-183`) | **`NOT_NEEDED_FOR_FIRST_BOOT`** | `[VERIFIED: source; INFERRED: path]` | CHDK SpyTask is commented out and no CHDK filesystem task is spawned (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:411-416`, line 414 comment, line 416 commented call); CHDK file access absent (`tools/port9b_runtime_contract.py:455-456`). No tracked U2 source defines CHDK flush/unmount or lock-use aspects, so none are triaged here. | **None (0 B)** |
| **U3** | `task_PhySw` keyboard interception entry & creator (`docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:142`) | **`NOT_NEEDED_FOR_FIRST_BOOT`** | `[INFERRED]` | Prototype launches unmodified stock `task_PhySw` (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:409`); keyboard interception disabled (`tools/port9b_runtime_contract.py:454`). Inspector does not use CHDK keyboard handling (`firmware/tools/witness_inspector_gm110c.m:52, 62, 185-188`). | **None (0 B)** |
| **U4(a)** | SpyTask launch site, priority, stack, gating, CPU mode, yield constraints (`tools/port13_oblig_u4.py:168-294, 310-325`, `OBLIG-U4-01..08, 10`) | **`NOT_NEEDED_FOR_FIRST_BOOT`** | `[VERIFIED]` | SpyTask is explicitly commented out in source (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:411-416`, line 416) for first-boot hardening; no CHDK tasks spawned (`tests/test_port9b_runtime_contract.py:86-89`). | **None (0 B)** |
| **U4(b)(i)** | Task-priority behaviour / RTOS scheduling policy (`tools/port13_oblig_u4.py:199-215`, `OBLIG-U4-03`) | **`NOT_NEEDED_FOR_FIRST_BOOT`** | `[VERIFIED: source; INFERRED: path]` | First boot does not include task-priority behaviour. `task_Startup_my` runs at fixed stock priority 0x19 (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:363`), SpyTask is disabled (`:416`), and boot stub modifies no scheduling policies (`tools/port9b_runtime_contract.py:457; tools/port13_oblig_u4.py:199-215`). | **None (0 B)** |
| **U4(b)(ii)** | Continuation branch runtime safety after tail branch (`tools/port13_oblig_u4.py:295-309`, `OBLIG-U4-09`) | **`NEEDED_FOR_FIRST_BOOT`** | `[UNKNOWN]` | Boot stub runs terminal branch `b.w sub_fc0d0126` at `chdk-port/platform/g3x/sub/110c/boot_prototype.c:434`. Inspector only runs if startup continues without stack corruption, exception, or hang (`tools/port13_oblig_u4.py:295-309`). Not ROM-closable: dynamic continuation execution safety (`requires_runtime_evidence=True`). Closed when camera keeps starting after stub branch and witness inspector runs and reports. | **None (0 B)** *(not ROM-closable)* |
| **U4(c)** | Warm-restart semaphores / kernel re-init teardown (`tools/port13_oblig_u4.py:326-341`, `OBLIG-U4-11`; `docs/RESTART_SD_HOST_AUDIT.md:11-29`; `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:80-82`) | **`NEEDED_FOR_FIRST_BOOT`** | `[UNKNOWN]` | DISKBOOT executes after stock firmware has initialized (`docs/RESTART_SD_HOST_AUDIT.md:11-29`). Candidate recreates kernel state (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:85-258`), but RAM copies do not prove inherited hardware/semaphore state is harmless (`docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:80-82`). Lingering semaphores could induce boot freeze (`tools/port13_oblig_u4.py:326-341`). Not ROM-closable: dynamic runtime state across warm restart (`requires_runtime_evidence=True`). Closed when camera completes kernel init without semaphore freeze and inspector runs and reports. | **None (0 B)** *(not ROM-closable)* |
| **Witness Addr** | Inspector / build witness-address alignment (`candidate_port2a/` @ `0x0035F7A0`) | **`NEEDED_FOR_FIRST_BOOT`** | `[VERIFIED: host binding; UNKNOWN: camera readout]` | Host binding completed and verified in builder (`tools/build_candidate_port2a.py:651-701, 830-833; docs/PORT16_CANDIDATE_BUILD.md:26`), which targets `0x0035F7A0` inside `candidate_port2a/` while preserving historical `firmware/tools/` artifacts. Physical observation on camera stays `[UNKNOWN]`. Not ROM-closable: host tooling binding. Closed when owner observes valid LCD readout without `ERR_READ` or invalid data (`firmware/tools/witness_inspector_payload.S:57-93`). | **None (0 B)** *(not ROM-closable)* |
| **Dual Markers & Script Activation** | Dual-flag VBR coexistence (`BOOTDISK` for loading candidate, `SCRIPT` for Canon Basic) & post-boot script execution (`docs/HANDOFF.md:435, 463; docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:20-25`) | **`NEEDED_FOR_FIRST_BOOT`** | `[UNKNOWN]` | SD VBR marker coexistence and post-boot script trigger are needed for inspector execution. Not ROM-closable: media and bootloader trigger dependency. Closed when owner boots dual-marker SD card and script executes (`firmware/tools/witness_inspector_gm110c.m:1-25; docs/HANDOFF.md:435, 463`). | **None (0 B)** *(not ROM-closable)* |
| **Witness Freshness** | Current-attempt witness freshness verification (`tools/build_candidate_port2a.py:783`, `firmware/tools/witness_inspector_payload.S:96-113, 165-174`, `firmware/tools/witness_inspector_gm110c.m:28`, `docs/HANDOFF.md:430, 466`, `docs/PORT3C_RESTART_READINESS_MATRIX.md:22-25`) | **`NEEDED_FOR_FIRST_BOOT`** | `[UNKNOWN]` | Candidate builder records fixed nonce `0x32A80001` (`tools/build_candidate_port2a.py:783`). Inspector payload logic explicitly excludes that constant from freshness proof (`firmware/tools/witness_inspector_payload.S:96-113`). Supplying a different or dynamic expected nonce does not close freshness; a dynamic challenge requires an independently established producer-side mechanism, which does not exist in the candidate. Not ROM-closable: dynamic anti-replay protocol gap. Item remains `UNKNOWN` until an independently established producer-side mechanism or independently verified DRAM memory-transition observation exists. | **None (0 B)** *(not ROM-closable)* |
| **Mode Transition** | Operational transition from Playback to Shooting Live View (`firmware/tools/witness_inspector_gm110c.m:185-188`, `docs/HANDOFF.md:1439`) | **`NEEDED_FOR_FIRST_BOOT`** | `[UNKNOWN]` | Retained LCDMsg descriptors remain in DRAM in Playback mode and render only upon transitioning to Shooting Live View. Not ROM-closable: physical camera operational procedure. Closed when owner operates mode switch to Shooting Live View and observes display lines (`firmware/tools/witness_inspector_gm110c.m:185-188; docs/HANDOFF.md:1439`). | **None (0 B)** *(not ROM-closable)* |

---

## 3. Detailed Bounded Analysis for U1–U4

### 3.1 Unknown U1: `CreateTask` Prologue Bytes and Replayed Literal (Interface I1)

#### 3.1.1 Problem Statement and Tracked Citations
- **Definition in PORT-9A**: `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:140` defines U1 as `"CreateTask prologue bytes and replayed literal [UNKNOWN; L1 contradicts itself]"` `[VERIFIED: docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:140]`. In Section 3 (`docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:38-55`), upstream CHDK task-creation interception (`CreateTask_my`) overwrites the RAM-resident `hook_CreateTask` in ATCM with an absolute jump to `CreateTask_my`, which checks task entry pointers, swaps in CHDK replacements, and replays the overwritten firmware prologue before resuming the stock kernel `[VERIFIED: docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:38-55]`.
- **Precondition Registration**: `tools/port9a_runtime_lifecycle.py:99` defines `create_task_prologue_verified: bool = False` in `Preconditions` `[VERIFIED: tools/port9a_runtime_lifecycle.py:99]`. In `tools/port9b_runtime_contract.py:77-78`, `U1` is registered as `"CreateTask prologue and continuation are STATIC_VERIFIED; runtime hook patch context and cache/IRQ safety"` `[VERIFIED: tools/port9b_runtime_contract.py:77-78]`.
- **Static ROM Resolution in PORT-11A**: Inspection of pinned slices `S1A`–`S1C` in `docs/PORT11A_GM110C_ROM_EVIDENCE.md:20, 61, 95-189, 401` resolved the static ROM prologue instruction at `0xBFE14A3C` and the replayed literal reference at `0xBFE14C58`, resolving the historical contradiction in tracked documentation `[VERIFIED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:20, 189]`.
- **Remaining Runtime Gap**: In `tools/port13_oblig_u4.py:184-198`, proof obligation `OBLIG-U4-02` establishes that runtime hook safety (modifying ATCM code at runtime, Harvard instruction cache/branch target buffer invalidation, IRQ safety) remains `UNKNOWN` `[VERIFIED: tools/port13_oblig_u4.py:184-198]`.

#### 3.1.2 Triage Decision
**`NOT_NEEDED_FOR_FIRST_BOOT`** `[VERIFIED]`

#### 3.1.3 Justification Against the Boot Path in the Corrected Source
1. **Direct Call to Stock DryOS CreateTask Veneer** `[VERIFIED]`: In Stage 4 (`sub_fc05b962_my()`), the boot stub spawns `task_Startup_my` by invoking the unmodified stock DryOS veneer at `0xFC31BBC4` (`docs/PORT11A_GM110C_ROM_EVIDENCE.md:61`):
   ```arm
   "    ldr     r0, =0xfc05b9a0\n"        // ROM literal string "Startup"
   "    blx     sub_fc31bbc4\n"           // DryOS CreateTask
   ```
   (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:364-365`, enclosed in parameter block `358-366`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:358-366; docs/PORT11A_GM110C_ROM_EVIDENCE.md:61]`.
2. **Strict Absence of Task-Creation Interception**: At no point in `chdk-port/platform/g3x/sub/110c/boot_prototype.c:1-436` does the boot stub install `CreateTask_my`, overwrite `hook_CreateTask`, or hook ATCM memory `[VERIFIED: docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:45; chdk-port/platform/g3x/sub/110c/boot_prototype.c:1-436]`. The contract suite in `tools/port9b_runtime_contract.py:453` validates as a mandatory source integrity invariant that `CreateTask_my` and `hook_CreateTask` are absent from active code:
   ```python
   "intercept": any(mentions(everything, n) for n in ("CreateTask_my", "hook_CreateTask")),
   ```
   (`tools/port9b_runtime_contract.py:453`) `[VERIFIED: tools/port9b_runtime_contract.py:453]`.
3. **Execution Path Independence**: Because the stock DryOS `CreateTask` implementation executes directly from ATCM without interception, first boot does not require replaying prologue instructions, patching ATCM, or synchronizing Harvard instruction caches at patch time `[INFERRED: operational behavior of stock DryOS task creation]`.
4. **Witness Completion**: In source code, both Stage 2 witness recording (`witness_record_core()` at `chdk-port/platform/g3x/sub/110c/boot_prototype.c:32-43, 170`) and Stage 3 witness recording (`witness_record_continuation()` at `chdk-port/platform/g3x/sub/110c/boot_prototype.c:45-56, 430`) execute without task-creation interception `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:32-56, 170, 430; tools/port9b_runtime_contract.py:453]`. Therefore, U1 is strictly not needed for first boot `[VERIFIED]`.

---

### 3.2 Unknown U2: `task_InitFileModules` Entry, Body, Stock Filesystem Readiness, and Storage Safety (Interface I2)

#### 3.2.1 Problem Statement and Tracked Citations
- **Definition in PORT-9A**: `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:141` defines U2 as `"`task_InitFileModules` entry and body [UNKNOWN]"` `[VERIFIED: docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:141]`. Section 3 (`docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:69-90`) specifies that GM1.10C task entry address and stock task body success/failure semantics were unestablished in repository records `[VERIFIED: docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:69-90]`.
- **Codification in Models**: `tools/port9a_runtime_lifecycle.py:100` defines `init_file_modules_entry_verified: bool = False` in `Preconditions` `[VERIFIED: tools/port9a_runtime_lifecycle.py:100]`. In `tools/port9b_runtime_contract.py:79-80`, `U2` is registered as `"InitFileModules entry is STATIC_VERIFIED; SD/FAT mount readiness and warm-restart storage safety"` `[VERIFIED: tools/port9b_runtime_contract.py:79-80]`.
- **Static ROM Resolution in PORT-11A**: In `docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 65, 219-267`, inspection of pinned slice `S2A` (`0xFC0BD070..0xFC0BD1BB`) statically verified task creator `sub_fc0bd0b4`, task name `"InitFileModules"`, priority `0x19`, stack size `0x1000`, and Thumb entry pointer `0xFC0BD071` (instruction address `0xFC0BD070`) `[VERIFIED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 247-267]`.
- **Remaining Runtime Obligations in PORT-13**: In `tools/port13_u2_obligations.py:599-806`, formal proof obligations govern U2 `[VERIFIED: tools/port13_u2_obligations.py:599-806]`:
  - `OBLIG-U2-01` (`tools/port13_u2_obligations.py:599-625`): Static task entry parameter and Thumb entry pointer `0xFC0BD071` (instruction address `0xFC0BD070`) are statically verified in GM1.10C ROM slice S2A (`kind=ObligationKind.STATIC`, `status=ObligationStatus.VERIFIED`) `[VERIFIED: tools/port13_u2_obligations.py:599-625; docs/PORT11A_GM110C_ROM_EVIDENCE.md:21, 247-267]`.
  - `OBLIG-U2-02` (`tools/port13_u2_obligations.py:628-649`): Dynamic task creation and scheduler dispatch execution witness confirming `task_InitFileModules` ran in the current boot generation (`kind=ObligationKind.RUNTIME`, `status=ObligationStatus.UNKNOWN`) `[VERIFIED: tools/port13_u2_obligations.py:628-649]`.
  - `OBLIG-U2-03` (`tools/port13_u2_obligations.py:652-678`): Current-generation normal completion witness confirming both `sub_fc0d9ccc` and `sub_fc0d9cf6` return normally in current boot generation (`kind=ObligationKind.RUNTIME`, `status=ObligationStatus.UNKNOWN`) `[VERIFIED: tools/port13_u2_obligations.py:652-678]`.
  - `OBLIG-U2-04` (`tools/port13_u2_obligations.py:680-704`): Event 0x5006 decoupling from filesystem I/O gate: Event(0x5006) does not imply FilesystemReady(SD0); independent kernel/storage state proof required (`kind=ObligationKind.RUNTIME`, status `UNKNOWN`) `[VERIFIED: tools/port13_u2_obligations.py:680-704]`.
  - `OBLIG-U2-05` (`tools/port13_u2_obligations.py:706-730`): Strict causal ordering of filesystem readiness signal prior to first CHDK file access with verified non-destructive open/read capability on mounted volume without contention or timeout (`kind=ObligationKind.RUNTIME`, status `UNKNOWN`) `[VERIFIED: tools/port13_u2_obligations.py:706-730]`.
  - `OBLIG-U2-06` (`tools/port13_u2_obligations.py:732-754`): Fail-closed fault, error, timeout, and out-of-order execution handling (`kind=ObligationKind.RUNTIME`, status `UNKNOWN`) `[VERIFIED: tools/port13_u2_obligations.py:732-754]`.
  - `OBLIG-U2-07` (`tools/port13_u2_obligations.py:757-779`): Monotonic `boot_generation` binding: filesystem readiness latch invalidated across soft reboot or warm restart (`kind=ObligationKind.RUNTIME`, status `UNKNOWN`) `[VERIFIED: tools/port13_u2_obligations.py:757-779]`.
  - `OBLIG-U2-08` (`tools/port13_u2_obligations.py:782-806`): Resolution of warm-restart SD host/card preconditions (P11, P12, P13, P15) with host retention qualified as plausible and reset ownership decoupled, confirming re-enumeration safety without bus lockup (`kind=ObligationKind.RUNTIME`, status `UNKNOWN`) `[VERIFIED: tools/port13_u2_obligations.py:782-806]`.
- **Architectural Separation of Facets** `[VERIFIED]`:
  To properly reflect the dependencies of first boot under the narrow definition, U2 is separated into two categories:
  - **Category (i) — Deferred CHDK Readiness Gate, CHDK Filesystem Assertions & CHDK-Side Consumption of InitFileModules Completion**:
    1. *Facet U2(a) — CHDK Readiness Gate / Hook / Latch*: Hooking `task_InitFileModules`, gating `core_spytask_can_start()`, intercepting filesystem initialization (`tools/port9b_runtime_contract.py:455-456`), and CHDK-side readiness latch semantics (`OBLIG-U2-06`, `OBLIG-U2-07` at `tools/port13_u2_obligations.py:732-779`) `[VERIFIED: tools/port9b_runtime_contract.py:455-456; tools/port13_u2_obligations.py:732-779]`.
    2. *Facet U2(b) — Deferred CHDK Filesystem Assertions & Mount State Preconditions*: Event 0x5006 decoupling (`OBLIG-U2-04`) and strict causal ordering of filesystem readiness signal prior to first CHDK file access (`OBLIG-U2-05` CHDK gate requirement, `tools/port13_u2_obligations.py:680-730`) `[VERIFIED: tools/port13_u2_obligations.py:680-730]`.
    3. *Facet U2(d)-CHDK — CHDK-Side SpyTask-Driven Consumption of InitFileModules Completion*: Upstream CHDK `core_spytask` clears `spytask_can_start`, waits up to 10 seconds for it to become 1, and on timeout continues and accesses fonts, scripts and configuration (`docs/PORT10A_RUNTIME_PRECONDITION_EVIDENCE.md:180-183`) `[VERIFIED: docs/PORT10A_RUNTIME_PRECONDITION_EVIDENCE.md:180-183]`. No tracked U2 obligation (`tools/port13_u2_obligations.py:599-806`) defines CHDK filesystem flush/unmount or CHDK lock use, so no such aspect is triaged under U2(d) `[VERIFIED: tools/port13_u2_obligations.py:599-806]`.
  - **Category (ii) — Stock SD Read Capability & Stock Filesystem Initialisation Needed by the Inspector**:
    4. *Facet U2(c) — Stock SD Read Capability & Warm-Restart SD Re-enumeration Without Bus Lockup*: Stock firmware capability to service read operations on `"A/WITNESS.BIN"` via `Fopen_Fut`, `Fread_Fut`, and `Fclose_Fut` (`firmware/tools/witness_inspector_gm110c.m:100-121`) and SD host controller/card re-enumeration confirming bus safety without lockup across warm restart (`tools/port13_u2_obligations.py:782-806`, `OBLIG-U2-08`) `[VERIFIED: firmware/tools/witness_inspector_gm110c.m:100-121; tools/port13_u2_obligations.py:782-806]`.
    5. *Facet U2(d)-stock — Stock `task_InitFileModules` Dispatch and Normal Completion*: Exactly the scope of the two PORT-13 obligations `[VERIFIED: tools/port13_u2_obligations.py:628-678]`:
       - `OBLIG-U2-02` statement: *"Dynamic task creation and scheduler dispatch execution witness confirming task_InitFileModules ran in the current boot generation"* (`tools/port13_u2_obligations.py:630-632`); required evidence `EXECUTION_WITNESS` that must show *"Dynamic execution trace confirming task_InitFileModules entry ran after DryOS scheduler dispatch in active boot generation context"* (`:637-641`); notes: *"Static ROM entry 0xFC0BD071 cannot discharge this runtime obligation."* (`:648`).
       - `OBLIG-U2-03` statement: *"Current-generation normal completion witness confirming both sub_fc0d9ccc and sub_fc0d9cf6 return normally in current boot generation (note: sub_fc0d9ccc r0==0 is constant on normal return and does NOT prove mount)"* (`tools/port13_u2_obligations.py:654-658`); required evidence `COMPLETION_WITNESS` (`:662-667`); notes: *"Requires dynamic completion witness for sub_fc0d9ccc and sub_fc0d9cf6 in active boot generation; r0==0 is constant on normal return and does not prove mount."* (`:676`).
       - Neither obligation mentions filesystem flush, unmount, or lock ownership `[VERIFIED: tools/port13_u2_obligations.py:628-678]`. Both concern the **stock** task and stock routines, not CHDK.

#### 3.2.2 Triage Decisions
- **Facet U2(a) (CHDK Readiness Gate / Hook / Latch)**: **`NOT_NEEDED_FOR_FIRST_BOOT`** `[VERIFIED]`
- **Facet U2(b) (Deferred CHDK Filesystem Assertions, `OBLIG-U2-04`, `OBLIG-U2-05` CHDK Gate)**: **`NOT_NEEDED_FOR_FIRST_BOOT`** `[VERIFIED: source; INFERRED: path]`
- **Facet U2(c) (Stock SD Read Capability & SD Re-enumeration Without Bus Lockup, `OBLIG-U2-08`)**: **`NEEDED_FOR_FIRST_BOOT`** `[UNKNOWN]` *(not ROM-closable, 0 B ROM ranges)*
- **Facet U2(d)-stock (Stock `task_InitFileModules` Dispatch and Normal Completion, `OBLIG-U2-02`, `OBLIG-U2-03`)**: **`NEEDED_FOR_FIRST_BOOT`** `[UNKNOWN]` *(not ROM-closable, 0 B ROM ranges)*
- **Facet U2(d)-CHDK (CHDK SpyTask-Driven Consumption of InitFileModules Completion, `docs/PORT10A_RUNTIME_PRECONDITION_EVIDENCE.md:180-183`)**: **`NOT_NEEDED_FOR_FIRST_BOOT`** `[VERIFIED: source; INFERRED: path]`

#### 3.2.3 Justification Against the Boot Path in the Corrected Source
1. **Justification for Category (i) — Deferred CHDK Readiness Gate, CHDK Filesystem Assertions & CHDK-Side Consumption of InitFileModules Completion (`NOT_NEEDED_FOR_FIRST_BOOT`)**:
   - **Facet U2(a) (CHDK Hook / Gate / Latch)** `[VERIFIED]`:
     - In Stage 5 (`task_Startup_my()`, `chdk-port/platform/g3x/sub/110c/boot_prototype.c:377-436`), the boot stub executes stock driver routines, optionally spawns `SD1stInit` via `sub_fc31b1f4` (`:397`), spawns stock `task_PhySw` via `sub_fc1283d2` (`:409`), records the continuation witness (`:430`), and executes the terminal branch `b.w sub_fc0d0126` (`:434`).
     - Nowhere in `chdk-port/platform/g3x/sub/110c/` does the source name `sub_fc0bd0b4` (the `InitFileModules` creator at `0xFC0BD0B4`, `docs/PORT11A_GM110C_ROM_EVIDENCE.md:65`), `task_InitFileModules` (`0xFC0BD070`, `docs/PORT11A_GM110C_ROM_EVIDENCE.md:65`), or `InitFileModules` `[VERIFIED]`.
     - In `task_Startup`, there is no direct call to `sub_fc0bd0b4` (`docs/PORT13_OBLIG_U4.md:70; docs/PORT11A_GM110C_ROM_EVIDENCE.md:238-239, 407`). Whether `task_InitFileModules` is reached indirectly via stock routines or continuation `b.w sub_fc0d0126` is `[UNKNOWN]`.
     - The decision for U2(a) does not rest on whether stock firmware dispatches `task_InitFileModules`. U2(a) concerns the CHDK hook, gate, and latch only. In source code, the CHDK replacement task, `core_spytask_can_start()`, and every CHDK file access are completely absent (`tools/port9b_runtime_contract.py:455-456; chdk-port/platform/g3x/sub/110c/boot_prototype.c:1-436`). Therefore, U2(a) is strictly `NOT_NEEDED_FOR_FIRST_BOOT` `[VERIFIED]`.
   - **Facet U2(b) (Deferred CHDK Filesystem Assertions, `OBLIG-U2-04/05` CHDK Gate)** `[VERIFIED: source; INFERRED: path]`:
     - Under the narrow definition of first boot, CHDK mount state preconditions and CHDK filesystem readiness gates are not included unless a cited line of the boot stub, the build, or the inspector actually depends on them `[VERIFIED]`.
     - The boot stub records `boot_witness` directly into DRAM (`.data` section at `0x0035F7A0`) via `witness_record_core()` (`:32-43`, `:170`) and `witness_record_continuation()` (`:45-56`, `:430`). CHDK SpyTask is completely commented out (`:411-416`). The boot stub contains zero filesystem calls, performs zero file accesses, and evaluates zero CHDK mount assertions (`tools/port9b_runtime_contract.py:455-456`).
     - Canon Basic's internal event procedures execute independently of CHDK filesystem gating and `OBLIG-U2-04/05` CHDK latch synchronization `[INFERRED]`. Therefore, U2(b) is `NOT_NEEDED_FOR_FIRST_BOOT` `[VERIFIED: source; INFERRED: path]`. Proposed ROM ranges: **None (0 B)**.
   - **Facet U2(d)-CHDK (CHDK SpyTask-Driven Consumption of InitFileModules Completion)** `[VERIFIED: source; INFERRED: path]`:
     - Scope source: upstream CHDK `core_spytask` clears `spytask_can_start = 0` at startup, waits up to 10 seconds for it to become 1, and on timeout continues and accesses fonts, scripts and configuration (`docs/PORT10A_RUNTIME_PRECONDITION_EVIDENCE.md:180-183`) `[VERIFIED: docs/PORT10A_RUNTIME_PRECONDITION_EVIDENCE.md:180-183]`. This is a CHDK-side consumer of the completion signal; it is distinct from the stock obligations `OBLIG-U2-02` / `OBLIG-U2-03`, which are triaged under U2(d)-stock in Category (ii).
     - The boot stub does not create SpyTask: the call is commented out, and the block comment states *"No CHDK keyboard, GUI, filesystem, or capture tasks are spawned."* (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:411-416`, comment at line 414, commented call at line 416) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:411-416]`. CHDK file access is absent (`tools/port9b_runtime_contract.py:455-456`).
     - The boot witness is written to DRAM by `witness_record_core()` / `witness_record_continuation()` (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:32-56, 170, 430`), not through any SpyTask path `[VERIFIED]`.
     - CHDK filesystem flush/unmount and CHDK lock use: no tracked U2 obligation defines them (`tools/port13_u2_obligations.py:599-806`), so no such sub-item is created; they are outside the narrow first-boot definition in any case (Section 1) `[VERIFIED: tools/port13_u2_obligations.py:599-806]`.
     - Therefore U2(d)-CHDK is `NOT_NEEDED_FOR_FIRST_BOOT` `[VERIFIED: source; INFERRED: path]`. Proposed ROM ranges: **None (0 B)**.

2. **Justification for Category (ii) — Facet U2(c): Stock SD Read Capability & SD Re-enumeration Without Bus Lockup (`NEEDED_FOR_FIRST_BOOT`)** `[UNKNOWN]`:
   - **Stock Read Dependency in Witness Inspector** `[VERIFIED: firmware/tools/witness_inspector_gm110c.m:100-121]`:
     - First boot requires that the boot witness become observable to the owner through the witness inspector `[VERIFIED]`.
     - In `firmware/tools/witness_inspector_gm110c.m`, the inspector script reads the compiled inspector payload binary `A/WITNESS.BIN` from the SD card using stock Canon Basic file I/O procedures:
       ```basic
       100: fh = Fopen_Fut("A/WITNESS.BIN", "rb")
       101: if fh = 0 then
       102:     LCDMsg_SetStr(h_title, "PORT-1G: ERR_OPEN")
       ...
       105:     exit sub
       106: end if
       ...
       109: read_sz = Fread_Fut(buf, 1, payload_size + 1, fh)
       110: cl = Fclose_Fut(fh)
       111: if read_sz <> payload_size then
       112:     LCDMsg_SetStr(h_title, "PORT-1G: ERR_READ")
       ...
       115:     exit sub
       116: end if
       117: if cl <> 0 then
       118:     LCDMsg_SetStr(h_title, "PORT-1G: ERR_CLOSE")
       ...
       121:     exit sub
       122: end if
       ```
       (`firmware/tools/witness_inspector_gm110c.m:100-121`) `[VERIFIED: firmware/tools/witness_inspector_gm110c.m:100-121]`.
     - If `Fopen_Fut`, `Fread_Fut`, or `Fclose_Fut` fails, the script exits immediately via `exit sub` (lines 105, 115, 121) before dispatching the payload at line 136 `[VERIFIED: firmware/tools/witness_inspector_gm110c.m:101-136]`.
   - **Stock Filesystem Initialisation Dependency**: triaged separately as Facet U2(d)-stock (item 3 below), so that `OBLIG-U2-02` / `OBLIG-U2-03` appear under exactly one sub-item `[VERIFIED]`.
   - **SD Re-enumeration Safety Across Warm Restart (`OBLIG-U2-08`)** `[VERIFIED: tools/port13_u2_obligations.py:782-806; docs/RESTART_SD_HOST_AUDIT.md:11-29]`:
     - Because `DISKBOOT.BIN` is loaded after initial stock firmware bootloader execution, the candidate restart executes as a warm restart (`docs/RESTART_SD_HOST_AUDIT.md:11-17`).
     - Proof obligation `OBLIG-U2-08` covers SD host controller and card re-enumeration across warm restart confirming bus safety without lockup (`tools/port13_u2_obligations.py:782-806`).
     - If the SD controller locks up or the stock driver fails to re-enumerate the card, the stock filesystem cannot service file reads, `Fopen_Fut` fails (`fh = 0`), and the witness inspector aborts without inspecting the witness.
   - **Decision and Sizing**:
     - Status: **`NEEDED_FOR_FIRST_BOOT`** `[UNKNOWN]`.
     - **Not ROM-Closable**: Dynamic SD controller re-enumeration across warm restart cannot be resolved by reading static ROM bytes; `OBLIG-U2-08` is declared `kind=ObligationKind.RUNTIME`, `status=ObligationStatus.UNKNOWN` with `WARM_RESTART_AUDIT_WITNESS` required evidence (`tools/port13_u2_obligations.py:788-791`). Static ROM reads cannot prove that hardware bus lockup will not occur across warm restart.
     - Proposed ROM ranges: **None (0 B)** *(not ROM-closable)*.
     - **Proposed observation for the owner trial plan `[INFERRED]`**: In the current attempt, the camera completes startup into Playback mode, the owner launches the witness inspector script, and the inspector's `Fopen_Fut("A/WITNESS.BIN", "rb")`, `Fread_Fut`, and `Fclose_Fut` succeed without error (`read_sz == payload_size`, `cl == 0`), showing that SD re-enumeration succeeded without bus lockup.

3. **Justification for Category (ii) — Facet U2(d)-stock: Stock `task_InitFileModules` Dispatch and Normal Completion (`OBLIG-U2-02`, `OBLIG-U2-03`) (`NEEDED_FOR_FIRST_BOOT`)** `[UNKNOWN]`:
   - **Scope**: exactly `OBLIG-U2-02` (stock `task_InitFileModules` dispatched by the DryOS scheduler in the current boot generation) and `OBLIG-U2-03` (stock `sub_fc0d9ccc` and `sub_fc0d9cf6` return normally in the current boot generation), as quoted in Section 3.2.1 `[VERIFIED: tools/port13_u2_obligations.py:628-678]`. Neither obligation concerns flush, unmount, lock ownership, or CHDK `[VERIFIED: tools/port13_u2_obligations.py:628-678]`.
   - **Why NEEDED, not deferred**: the inspector reads `A/WITNESS.BIN` with stock `Fopen_Fut` / `Fread_Fut` / `Fclose_Fut` and aborts via `exit sub` if any fails (`firmware/tools/witness_inspector_gm110c.m:100-121`) `[VERIFIED]`. Whether those stock reads depend on stock `task_InitFileModules` having been dispatched and having completed normally cannot be shown from the cited source `[UNKNOWN]`. The absence of CHDK file operations (`tools/port9b_runtime_contract.py:455-456`) is not evidence that stock reads do not depend on stock initialisation `[VERIFIED]`. No cited line of the boot stub (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:377-436`), the build (`tools/build_candidate_port2a.py:651-701, 830-833`) or the inspector (`firmware/tools/witness_inspector_gm110c.m:100-121`) shows that first boot does not depend on it, so it is not deferred `[VERIFIED: absence in cited lines]`.
   - **Reachability**: the boot stub does not call the creator `sub_fc0bd0b4` directly; whether stock `task_InitFileModules` is reached via the stock routines or the continuation `b.w sub_fc0d0126` is `[UNKNOWN]` (`docs/PORT13_OBLIG_U4.md:70; docs/PORT11A_GM110C_ROM_EVIDENCE.md:238-239, 407; chdk-port/platform/g3x/sub/110c/boot_prototype.c:434`).
   - **Not ROM-Closable**: both obligations are `kind=ObligationKind.RUNTIME`, `status=ObligationStatus.UNKNOWN` (`tools/port13_u2_obligations.py:634-635, 659-660`), require an `EXECUTION_WITNESS` / `COMPLETION_WITNESS` (`:637, 662`), and record that static ROM entry evidence cannot discharge them and that `r0==0` on return does not prove mount (`:648, 676`). Reading ROM bytes therefore cannot close U2(d)-stock.
   - Proposed ROM ranges: **None (0 B)** *(not ROM-closable)*.
   - **Proposed observation for the owner trial plan `[INFERRED]`**: Closure is split into two distinct parts:
     - *(a) Functional first-boot observation*: In the same attempt, all three inspector file operations (open, read and close) succeed (`fh <> 0`, `read_sz == payload_size`, `cl == 0` at `firmware/tools/witness_inspector_gm110c.m:100-121`). Reaching the stock UI alone does not establish this, because the inspector can abort on any failure (`firmware/tools/witness_inspector_gm110c.m:100-121`). This answers only the functional first-boot question (whether stock file reading functioned during the trial); label: functional first-boot observation `[INFERRED]`.
     - *(b) Discharge of the canonical obligations*: Discharging `OBLIG-U2-02` and `OBLIG-U2-03` requires the specific observations defined in `tools/port13_u2_obligations.py:628-678`: current-generation dynamic task creation and scheduler dispatch execution evidence confirming `task_InitFileModules` ran in the active boot generation context (`:630-642`), and current-generation normal completion evidence confirming both `sub_fc0d9ccc` and `sub_fc0d9cf6` returned in the current boot generation without latched fault (`:654-668`).
     - *Separation and status*: Observation (a) does NOT discharge (b). Inspector file operations succeeding does not prove scheduler dispatch of `task_InitFileModules` or normal completion of `sub_fc0d9ccc` / `sub_fc0d9cf6`. Therefore, `OBLIG-U2-02` and `OBLIG-U2-03` stay `[UNKNOWN]` after a successful first boot unless (b) is specifically observed.

---

### 3.3 Unknown U3: `task_PhySw` Entry, Creator `0xFC1283D2`, and Keyboard Interception (Interface I4)

#### 3.3.1 Problem Statement and Tracked Citations
- **Definition in PORT-9A**: `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:142` defines U3 as `"task_PhySw entry independently of E; meaning of 0xFC1283D2 [UNKNOWN / INFERRED]"` `[VERIFIED: docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:142]`. Upstream CHDK intercepts `task_PhySw` via `CreateTask_my` to substitute `mykbd_task` and `wrap_kbd_p1_f`, enlarging task stack to `0x2000` to handle CHDK ALT-mode key events (`docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:107-135`) `[VERIFIED: docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:107-135]`.
- **Precondition Registration**: `tools/port9a_runtime_lifecycle.py:101` defines `physw_entry_verified: bool = False` in `Preconditions` `[VERIFIED: tools/port9a_runtime_lifecycle.py:101]`. In `tools/port9b_runtime_contract.py:81-82`, `U3` is registered as `"PhySw creator, entry and CreateTaskStrictly chain are STATIC_VERIFIED; runtime replacement and stack safety"` `[VERIFIED: tools/port9b_runtime_contract.py:81-82]`.
- **Static ROM Resolution in PORT-11A**: In `docs/PORT11A_GM110C_ROM_EVIDENCE.md:22, 67, 310-385`, inspection of pinned slices `S3A` (`0xFC1283AC..0xFC1283FF`) and `S3B` (`0xFC128704..0xFC12871F`) verified `0xFC1283D2` as the creator subroutine that passes task name `"PhySw"`, priority `0x17` (`23` dec), stack size `0x800`, and Thumb entry pointer `0xFC1283AD` to `j_CreateTaskStrictly` (`0xFC31BE8C`), resolving the role of `0xFC1283D2` `[VERIFIED: docs/PORT11A_GM110C_ROM_EVIDENCE.md:22, 67, 345-385]`.
- **Status in Source**: Tracked source files explicitly document that keyboard interception is intentionally disabled in the prototype (`vendor/g3x-platform/platform/g3x/kbd.c:47-49`; `docs/PORT7B_PLAYBACK_MASK_CORRECTION.md:122`; `tools/port9b_runtime_contract.py:454`) `[VERIFIED: docs/PORT7B_PLAYBACK_MASK_CORRECTION.md:122; tools/port9b_runtime_contract.py:454]`.

#### 3.3.2 Triage Decision
**`NOT_NEEDED_FOR_FIRST_BOOT`** `[INFERRED]`

#### 3.3.3 Justification Against the Boot Path in the Corrected Source
1. **Unmodified Stock PhySw Launch** `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:409]`: In Stage 5 (`task_Startup_my()`), the boot stub launches stock `task_PhySw` directly by calling its stock creator:
   ```arm
   // Launch unmodified stock task_PhySw (keyboard task hook remains disabled)
   "    bl      sub_fc1283d2\n"
   ```
   (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:408-409`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:408-409]`.
2. **Strict Absence of Keyboard Interception** `[VERIFIED: tools/port9b_runtime_contract.py:454]`: The contract suite in `tools/port9b_runtime_contract.py:454` validates that `mykbd_task` is absent from active source:
   ```python
   "kbd": defines_function(everything, rt.REPLACEMENTS["PhySw"]),
   ```
   (`tools/port9b_runtime_contract.py:454`) `[VERIFIED: tools/port9b_runtime_contract.py:454]`. The prototype executes stock firmware key scanning without interception `[VERIFIED]`.
3. **Observation Independence**: The witness inspector script `firmware/tools/witness_inspector_gm110c.m` executes via native Canon Basic scripting in Playback mode and displays in Shooting Live View upon mode transition (`firmware/tools/witness_inspector_gm110c.m:52, 62, 185-188; docs/HANDOFF.md:1439`). It does not rely on CHDK ALT-mode key handling, keyboard routing, or key event interception `[INFERRED]`. Therefore, U3 is not needed for first boot `[INFERRED]`.

---

### 3.4 Unknown U4: SpyTask Creation Point, Priority, and Launch Dependencies (Interface I3)

#### 3.4.1 Problem Statement and Tracked Citations
- **Definition in PORT-9A**: `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:143` defines U4 as `"SpyTask creation point and priority on GM1.10C [UNKNOWN]"` `[VERIFIED: docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:143]`. Section 3 (`docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:91-106`) notes that upstream CHDK spawns `SpyTask` after startup, but running `SpyTask` prematurely without filesystem readiness results in a 10-second timeout unhooked crash `[VERIFIED: docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:91-106]`.
- **Contract Codification**: `tools/port9b_runtime_contract.py:83-84` registers U4 as `"SpyTask creation point, priority and readiness dependencies on GM1.10C"` `[VERIFIED: tools/port9b_runtime_contract.py:83-84]`.
- **Codification of 11 Formal Obligations in PORT-13**: In `tools/port13_oblig_u4.py:168-341`, milestone PORT-13 established 11 canonical fail-closed proof obligations for U4 `[VERIFIED: tools/port13_oblig_u4.py:168-341; docs/PORT13_OBLIG_U4.md:50-61]`:
  - `OBLIG-U4-01` (`tools/port13_oblig_u4.py:168-183`): SpyTask launch site and caller execution ordering in GM1.10C startup sequence (`requires_runtime_evidence=True`, status `UNKNOWN`) `[VERIFIED: tools/port13_oblig_u4.py:168-183]`.
  - `OBLIG-U4-02` (`tools/port13_oblig_u4.py:184-198`): Runtime hook placement and CreateTask interception authorization (Contract I1) (`requires_runtime_evidence=True`, status `UNKNOWN`) `[VERIFIED: tools/port13_oblig_u4.py:184-198]`.
  - `OBLIG-U4-03` (`tools/port13_oblig_u4.py:199-215`): RTOS scheduling priority assignment and kernel scheduler policy validation (`requires_runtime_evidence=False`, status `UNKNOWN`) `[VERIFIED: tools/port13_oblig_u4.py:199-215]`.
  - `OBLIG-U4-04` (`tools/port13_oblig_u4.py:216-231`): Task stack sizing and DryOS dynamic memory pool ownership validation (`requires_runtime_evidence=False`, status `UNKNOWN`) `[VERIFIED: tools/port13_oblig_u4.py:216-231]`.
  - `OBLIG-U4-05` (`tools/port13_oblig_u4.py:232-247`): Filesystem readiness gating and monotonic latch synchronization (Contract I3) (`requires_runtime_evidence=True`, status `UNKNOWN`) `[VERIFIED: tools/port13_oblig_u4.py:232-247]`.
  - `OBLIG-U4-06` (`tools/port13_oblig_u4.py:248-262`): Fail-closed gate timeout enforcement eliminating upstream CHDK legacy bypass (`requires_runtime_evidence=False`, status `UNKNOWN`) `[VERIFIED: tools/port13_oblig_u4.py:248-262]`.
  - `OBLIG-U4-07` (`tools/port13_oblig_u4.py:263-278`): Isolation of legacy timeout-bypass causal claim (storage corruption / kernel panic) (`requires_runtime_evidence=True`, status `UNKNOWN`) `[VERIFIED: tools/port13_oblig_u4.py:263-278]`.
  - `OBLIG-U4-08` (`tools/port13_oblig_u4.py:279-294`): Task execution CPU mode and interrupt mask conformance (Privileged Supervisor Mode) (`requires_runtime_evidence=False`, status `UNKNOWN`, evaluated in `docs/PORT14_Q_U4_08.md:1-85`) `[VERIFIED: tools/port13_oblig_u4.py:279-294]`.
  - `OBLIG-U4-09` (`tools/port13_oblig_u4.py:295-309`): Continuation branch runtime safety (tail branch `sub_fc0d0126`) (`requires_runtime_evidence=True`, status `UNKNOWN`) `[VERIFIED: tools/port13_oblig_u4.py:295-309]`. Definition text:
    > statement: *"Continuation branch runtime safety (tail branch sub_fc0d0126)"*  
    > required_evidence: *"Runtime proof that executing the tail branch b.w sub_fc0d0126 (boot_prototype.c:434) successfully continues startup without stack corruption, CPU exception, or hang."* (`tools/port13_oblig_u4.py:297, 301-303`)  
  - `OBLIG-U4-10` (`tools/port13_oblig_u4.py:310-325`): SpyTask cooperative yield behavior and global-interrupt disable constraints (`requires_runtime_evidence=True`, status `UNKNOWN`) `[VERIFIED: tools/port13_oblig_u4.py:310-325]`.
  - `OBLIG-U4-11` (`tools/port13_oblig_u4.py:326-341`): Isolation of warm-restart semaphore-freeze hypothesis across reboot (`requires_runtime_evidence=True`, status `UNKNOWN`) `[VERIFIED: tools/port13_oblig_u4.py:326-341]`. Definition text:
    > statement: *"Isolation of warm-restart semaphore-freeze hypothesis across reboot (Finding C18 / Remediation #9)"*  
    > required_evidence: *"Empirical reboot trace or kernel teardown analysis demonstrating whether lingering semaphores from aborted tasks induce a boot freeze during warm restart, or if kernel re-initialization cleanly resets Low RAM OS structures."* (`tools/port13_oblig_u4.py:328, 332-335`)  
- **Separation into Three Architectural Facets** `[VERIFIED]`:
  1. *Facet U4(a) — SpyTask Lifecycle & Launch Obligations*: Obligations specific to SpyTask creation, priority, stack, gating, CPU mode, yield constraints, and timeout bypass (`OBLIG-U4-01..08, 10`) `[VERIFIED: tools/port13_oblig_u4.py:168-294, 310-325]`.
  2. *Facet U4(b) — Task-Priority Behaviour & Continuation Branch Safety*:
     - *Sub-item U4(b)(i) — Priority Policy (`OBLIG-U4-03`)*: RTOS scheduling priority assignment and kernel scheduler policy validation (`tools/port13_oblig_u4.py:199-215`) `[VERIFIED: tools/port13_oblig_u4.py:199-215]`.
     - *Sub-item U4(b)(ii) — Continuation Safety After Branch (`OBLIG-U4-09`)*: Runtime execution safety across tail branch `b.w sub_fc0d0126` (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:434; tools/port13_oblig_u4.py:295-309`) `[VERIFIED: tools/port13_oblig_u4.py:295-309]`.
  3. *Facet U4(c) — Warm-Restart Semaphores / Kernel Re-init Teardown*: Isolation of warm-restart semaphore freeze hypothesis across reboot (`OBLIG-U4-11`, `tools/port13_oblig_u4.py:326-341`) `[VERIFIED: tools/port13_oblig_u4.py:326-341]`.

#### 3.4.2 Triage Decisions
- **Facet U4(a) (SpyTask Lifecycle & Launch Obligations)**: **`NOT_NEEDED_FOR_FIRST_BOOT`** `[VERIFIED]`
- **Sub-item U4(b)(i) (Task-Priority Behaviour / Priority Policy, `OBLIG-U4-03`)**: **`NOT_NEEDED_FOR_FIRST_BOOT`** `[VERIFIED: source; INFERRED: path]`
- **Sub-item U4(b)(ii) (Continuation Safety After Branch, `OBLIG-U4-09`)**: **`NEEDED_FOR_FIRST_BOOT`** `[UNKNOWN]` *(not ROM-closable, 0 B ROM ranges)*
- **Facet U4(c) (Warm-Restart Semaphores / Kernel Re-init Teardown, `OBLIG-U4-11`)**: **`NEEDED_FOR_FIRST_BOOT`** `[UNKNOWN]` *(not ROM-closable, 0 B ROM ranges)*

#### 3.4.3 Justification Against the Boot Path in the Corrected Source
1. **Justification for U4(a) (SpyTask Lifecycle & Launch Obligations — NOT_NEEDED_FOR_FIRST_BOOT)** `[VERIFIED]`:
   - **SpyTask Completely Disabled in Prototype Source** `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:411-416]`: In Stage 5 (`task_Startup_my()`), `CreateTask_spytask` is explicitly commented out and disabled:
     ```c
     // ---------------------------------------------------------------------
     // CHDK SpyTask Completely Disabled for First-Boot Hardening (PORT-1C.2)
     // Prevents premature thread execution and 10-second timeout unhooked crash.
     // No CHDK keyboard, GUI, filesystem, or capture tasks are spawned.
     // ---------------------------------------------------------------------
     // "    bl      CreateTask_spytask\n"
     ```
     (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:411-416`, commented line 416) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:411-416]`.
   - **Contract Enforced Absence** `[VERIFIED: tools/port9b_runtime_contract.py:457]`: In `tools/port9b_runtime_contract.py:457`, the contract enforces:
     ```python
     "spytask": has_spytask_activation_marker(sources),
     ```
     confirming that no active reference to `CreateTask_spytask` exists in active source (`tests/test_port9b_runtime_contract.py:86-89`) `[VERIFIED: tools/port9b_runtime_contract.py:457; tests/test_port9b_runtime_contract.py:86-89]`.
   - **Execution Bypass**: Because SpyTask is completely commented out in source code, obligations `OBLIG-U4-01` through `OBLIG-U4-08` and `OBLIG-U4-10` do not lie on the execution path to first boot `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:411-416]`.

2. **Justification for U4(b)(i) (Priority Policy, `OBLIG-U4-03` — NOT_NEEDED_FOR_FIRST_BOOT)** `[VERIFIED: source; INFERRED: path]`:
   - **Narrow Definition Application**: First boot does NOT include task-priority behaviour or RTOS scheduling policy validation (`OBLIG-U4-03`), unless a cited line of the boot stub, the build or the inspector actually depends on them `[VERIFIED]`.
   - **Fixed Task Priority in Boot Stub** `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:358-366]`: In Stage 4 (`sub_fc05b962_my()`), `task_Startup_my` is created with fixed priority `0x19` (25 decimal), exactly matching stock Canon firmware:
     ```arm
     "    movs    r1, #0x19\n"              // Task priority 25
     "    ldr     r0, =0xfc05b9a0\n"        // ROM literal string "Startup"
     "    blx     sub_fc31bbc4\n"           // DryOS CreateTask
     ```
     (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:363-365`). The boot stub never invokes dynamic priority changes, modifies task scheduling policy, or alters task priorities (`tools/port13_oblig_u4.py:199-215`).
   - **Absence of Competing Background Tasks** `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:411-416]`: Because SpyTask is commented out (`:411-416`), no competing CHDK threads run during first boot.
   - **Decision**: Neither the boot stub, nor the build, nor the inspector depends on task-priority policy. Therefore, U4(b)(i) is **`NOT_NEEDED_FOR_FIRST_BOOT`** `[VERIFIED: source; INFERRED: path]`. Proposed ROM ranges: **None (0 B)**.

3. **Justification for U4(b)(ii) (Continuation Safety After Branch, `OBLIG-U4-09` — NEEDED_FOR_FIRST_BOOT)** `[UNKNOWN]`:
   - **Execution of Continuation Branch** `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:430-434]`:
     In Stage 5 (`task_Startup_my()`), after recording the continuation witness (`bl witness_record_continuation` at line 430), the boot stub pops preserved registers at line 433 and executes the terminal branch:
     ```arm
     "    b.w     sub_fc0d0126\n"
     ```
     (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:434`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:430-434]`.
   - **Critical Dependency of Witness Observability**:
     The definition of `OBLIG-U4-09` in `tools/port13_oblig_u4.py:295-309` is strictly about continuing startup without corruption, exception, or hang:
     > *"Runtime proof that executing the tail branch b.w sub_fc0d0126 (boot_prototype.c:434) successfully continues startup without stack corruption, CPU exception, or hang."* (`tools/port13_oblig_u4.py:301-303`)  
     The boot stub runs this branch at `chdk-port/platform/g3x/sub/110c/boot_prototype.c:434`. The witness inspector only runs if Canon firmware startup successfully continues through this branch into Playback mode. If branching to `sub_fc0d0126` encounters a misaligned stack, corrupt register, CPU exception, or hang, startup halts and the witness inspector cannot run.
   - **Decision and Sizing**:
     - Status: **`NEEDED_FOR_FIRST_BOOT`** `[UNKNOWN]`.
     - **Not ROM-Closable**: Runtime execution safety across the continuation branch cannot be proven by reading static ROM bytes. It is governed by runtime obligation `OBLIG-U4-09` (`requires_runtime_evidence=True`, `tools/port13_oblig_u4.py:308`).
     - Proposed ROM ranges: **None (0 B)** *(not ROM-closable)*.
     - **Proposed observation for the owner trial plan `[INFERRED]`**: The camera keeps starting after the boot stub's terminal branch `b.w sub_fc0d0126` (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:434`), startup completes normally into Playback mode, and the witness inspector runs and reports.

4. **Justification for U4(c) (Warm-Restart Semaphores / Kernel Re-init Teardown, `OBLIG-U4-11` — NEEDED_FOR_FIRST_BOOT)** `[UNKNOWN]`:
   - **Removal of Clean Cold-Start Premise** `[VERIFIED: docs/RESTART_SD_HOST_AUDIT.md:11-29; docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:80-82]`:
     - DISKBOOT does not execute from a clean cold-start hardware reset state. Instead, `DISKBOOT.BIN` is loaded after stock firmware initialization has already executed (`StartDiskboot` at `0xFC05BBEA`; `docs/RESTART_SD_HOST_AUDIT.md:11-17`).
     - The candidate boot stub then re-executes DryOS kernel initialization (`sub_fc31b408` at `chdk-port/platform/g3x/sub/110c/boot_prototype.c:252`), recreating kernel data structures in DRAM (`:85-258`).
     - As demonstrated in `docs/RESTART_SD_HOST_AUDIT.md:21-24` and `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:80-82`, RAM copy loops and BSS zeroing reset software state in RAM, but they do NOT show that the inherited hardware, peripheral, and RTOS state is harmless.
   - **Kernel Freeze Risk from Lingering Semaphores (`OBLIG-U4-11`)**:
     - `OBLIG-U4-11` (`tools/port13_oblig_u4.py:326-341`) isolates whether lingering semaphores from aborted pre-restart tasks induce a boot freeze during warm restart, or if kernel re-initialization cleanly resets Low RAM OS structures without deadlocking.
     - If lingering semaphores induce a boot freeze during DryOS kernel re-initialization, the boot stub halts, startup never completes, and the witness inspector cannot run.
   - **Decision and Sizing**:
     - Status: **`NEEDED_FOR_FIRST_BOOT`** `[UNKNOWN]`.
     - **Not ROM-Closable**: Whether lingering semaphores induce a freeze across the warm restart boundary is an unresolved dynamic runtime question (`requires_runtime_evidence=True`, `tools/port13_oblig_u4.py:340; docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:80-82`). Reading static ROM bytes cannot demonstrate dynamic teardown behavior or convergence of inherited hardware/semaphore state.
     - Proposed ROM ranges: **None (0 B)** *(not ROM-closable)*.
     - **Proposed observation for the owner trial plan `[INFERRED]`**: The camera completes repeated DryOS kernel initialization without freezing or hanging on lingering semaphores, allowing startup to proceed through `task_Startup_my` to continuation, where the witness inspector runs and reports.

---

## 4. Minimal ROM Ranges for NEEDED Items & Open-Items Inventory

### 4.1 First-Boot ROM-Range Evaluation Table

Per the triage decisions established in Sections 2 and 3 under the narrow first-boot definition `[VERIFIED]`:
- U1 is **`NOT_NEEDED_FOR_FIRST_BOOT`** `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:358-366; tools/port9b_runtime_contract.py:453]`.
- U2(a) is **`NOT_NEEDED_FOR_FIRST_BOOT`** `[VERIFIED: tools/port9b_runtime_contract.py:455-456; chdk-port/platform/g3x/sub/110c/boot_prototype.c:377-436; docs/PORT13_OBLIG_U4.md:70; docs/PORT11A_GM110C_ROM_EVIDENCE.md:239, 407]`.
- U2(b) is **`NOT_NEEDED_FOR_FIRST_BOOT`** `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:27-29, 39, 52, 411-416; tools/port9b_runtime_contract.py:455-456; tools/port13_u2_obligations.py:680-730]`.
- U2(c) is **`NEEDED_FOR_FIRST_BOOT`** with status **`UNKNOWN`** (stock SD read capability for inspector and SD re-enumeration without bus lockup, `OBLIG-U2-08`; not ROM-closable) `[UNKNOWN: firmware/tools/witness_inspector_gm110c.m:100-121; tools/port13_u2_obligations.py:782-806]`.
- U2(d)-stock is **`NEEDED_FOR_FIRST_BOOT`** with status **`UNKNOWN`** (stock `task_InitFileModules` dispatch and normal completion, `OBLIG-U2-02`, `OBLIG-U2-03`; not ROM-closable) `[UNKNOWN: tools/port13_u2_obligations.py:628-678; firmware/tools/witness_inspector_gm110c.m:100-121]`.
- U2(d)-CHDK is **`NOT_NEEDED_FOR_FIRST_BOOT`** (CHDK SpyTask-driven consumption of InitFileModules completion) `[VERIFIED: docs/PORT10A_RUNTIME_PRECONDITION_EVIDENCE.md:180-183; chdk-port/platform/g3x/sub/110c/boot_prototype.c:411-416]`.
- U3 is **`NOT_NEEDED_FOR_FIRST_BOOT`** `[INFERRED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:409; tools/port9b_runtime_contract.py:454]`.
- U4(a) is **`NOT_NEEDED_FOR_FIRST_BOOT`** `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:411-416; tests/test_port9b_runtime_contract.py:86-89]`.
- U4(b)(i) is **`NOT_NEEDED_FOR_FIRST_BOOT`** `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:358-366, 411-416; tools/port9b_runtime_contract.py:457; tools/port13_oblig_u4.py:199-215]`.
- U4(b)(ii) is **`NEEDED_FOR_FIRST_BOOT`** with status **`UNKNOWN`** (continuation branch runtime safety; not ROM-closable) `[UNKNOWN: tools/port13_oblig_u4.py:295-309; chdk-port/platform/g3x/sub/110c/boot_prototype.c:434]`.
- U4(c) is **`NEEDED_FOR_FIRST_BOOT`** with status **`UNKNOWN`** (warm-restart semaphore teardown; not ROM-closable) `[UNKNOWN: tools/port13_oblig_u4.py:326-341; docs/RESTART_SD_HOST_AUDIT.md:11-29; docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:80-82]`.
- Inspector / build witness-address alignment is **`NEEDED_FOR_FIRST_BOOT`** `[VERIFIED: host binding; UNKNOWN: camera readout]` (host-side binding completed in `candidate_port2a/`; not ROM-closable).
- Dual-flag boot marker coexistence and post-boot script activation is **`NEEDED_FOR_FIRST_BOOT`** with status **`UNKNOWN`** (media/script trigger gap; not ROM-closable) `[INFERRED]`.
- Current-attempt witness freshness verification is **`NEEDED_FOR_FIRST_BOOT`** with status **`UNKNOWN`** (candidate records fixed nonce per `tools/build_candidate_port2a.py:783` excluded from freshness proof per `firmware/tools/witness_inspector_payload.S:96-113`; dynamic challenge needs independently established producer-side mechanism not in candidate; not ROM-closable) `[UNKNOWN]`.
- Stock Playback-to-Shooting Live View mode transition is **`NEEDED_FOR_FIRST_BOOT`** with status **`UNKNOWN`** (physical operational dependency; not ROM-closable) `[INFERRED]`.

All eight prerequisite items needed for first boot are non-ROM dependencies (four dynamic runtime hardware/RTOS/stock-initialisation questions, one host-side build metadata alignment item, one SD card VBR marker coexistence dependency, one dynamic anti-replay challenge protocol gap, and one physical operational UI mode transition). Exactly **0 ROM ranges** are needed or proposed (totaling **0 bytes**) `[VERIFIED]`:

| Item ID | Start Address | Length (Bytes) | Purpose | Address Source Citation | Epistemic Status |
|---|---|---:|---|---|:---:|
| *(None)* | — | 0 B | No ROM ranges closable via static ROM reads: all 8 needed items are dynamic runtime, operational, or host build dependencies marked 'not ROM-closable'. | — | `VERIFIED` |

- **Individual Range Constraint**: $0\text{ B} \le 512\text{ B}$ (satisfies requirement) `[VERIFIED]`.
- **Cumulative Total Constraint**: $0\text{ B} \le 4096\text{ B}$ (satisfies requirement) `[VERIFIED]`.

---

### 4.2 Open Items Needed for First Boot but with No Closable Range

Under the narrow first-boot definition, exactly **eight open needed items** exist for first boot. None of them is a ROM unknown, and each is explicitly marked **not ROM-closable** with its reason, an `[UNKNOWN]` label (or `[VERIFIED: host binding; UNKNOWN: camera readout]` for host build metadata alignment `[VERIFIED]`), and the specific proposed observation for the owner trial plan that would close it `[VERIFIED]`:

1. **Item 1 — Stock SD Read Capability & SD Re-enumeration Without Bus Lockup (`U2(c)`, `OBLIG-U2-08`)** `[UNKNOWN]`:
   - **Status / Classification**: **`NEEDED_FOR_FIRST_BOOT`** `[UNKNOWN]`, **not ROM-closable**.
   - **Citations**: `firmware/tools/witness_inspector_gm110c.m:100-121`; `tools/port13_u2_obligations.py:782-806`; `docs/RESTART_SD_HOST_AUDIT.md:11-29`.
   - **Reason Not ROM-Closable**: The witness inspector script aborts via `exit sub` before executing or inspecting if `Fopen_Fut`, `Fread_Fut`, or `Fclose_Fut` fails on `"A/WITNESS.BIN"` (`firmware/tools/witness_inspector_gm110c.m:100-121`). `OBLIG-U2-08` covers SD host and card re-enumeration across warm restart without bus lockup (`tools/port13_u2_obligations.py:782-806`). Dynamic controller state across warm restart cannot be closed by reading static ROM bytes (`kind=ObligationKind.RUNTIME`, `tools/port13_u2_obligations.py:788`).
   - **Proposed observation for the owner trial plan `[INFERRED]`**: In the current attempt, the camera completes startup into Playback mode, the owner launches the witness inspector script, and the inspector's `Fopen_Fut("A/WITNESS.BIN", "rb")`, `Fread_Fut`, and `Fclose_Fut` succeed without error (`read_sz == payload_size`, `cl == 0`), showing that SD re-enumeration succeeded without bus lockup.

2. **Item 2 — Continuation Branch Runtime Safety After Tail Branch (`U4(b)(ii)`, `OBLIG-U4-09`)** `[UNKNOWN]`:
   - **Status / Classification**: **`NEEDED_FOR_FIRST_BOOT`** `[UNKNOWN]`, **not ROM-closable**.
   - **Citations**: `chdk-port/platform/g3x/sub/110c/boot_prototype.c:434`; `tools/port13_oblig_u4.py:295-309`.
   - **Reason Not ROM-Closable**: The boot stub executes the terminal branch `b.w sub_fc0d0126` at line 434 (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:434`). The witness inspector only runs if Canon firmware startup continues without stack corruption, CPU exception, or hang (`tools/port13_oblig_u4.py:295-309`). Dynamic continuation execution safety across the branch cannot be settled by reading static ROM bytes (`requires_runtime_evidence=True`).
   - **Proposed observation for the owner trial plan `[INFERRED]`**: The camera keeps starting after the stub's terminal branch `b.w sub_fc0d0126` without crashing or hanging, reaches Playback mode, and the witness inspector runs and reports.

3. **Item 3 — Warm-Restart Semaphores / Kernel Re-init Teardown (`U4(c)`, `OBLIG-U4-11`)** `[UNKNOWN]`:
   - **Status / Classification**: **`NEEDED_FOR_FIRST_BOOT`** `[UNKNOWN]`, **not ROM-closable**.
   - **Citations**: `tools/port13_oblig_u4.py:326-341`; `docs/RESTART_SD_HOST_AUDIT.md:11-29`; `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:80-82`.
   - **Reason Not ROM-Closable**: `DISKBOOT.BIN` executes as a warm restart after stock firmware initialization (`docs/RESTART_SD_HOST_AUDIT.md:11-29`). The candidate boot stub recreates kernel state (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:85-258`), but RAM copy loops do not prove that lingering semaphores from aborted pre-restart tasks are harmless (`docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:80-82`). If lingering semaphores induce a boot freeze (`OBLIG-U4-11`), startup halts and the inspector cannot run. Lingering RTOS state across warm restart cannot be resolved by static ROM reads (`requires_runtime_evidence=True`).
   - **Proposed observation for the owner trial plan `[INFERRED]`**: The camera executes repeated DryOS kernel initialization without freezing or hanging on lingering semaphores, allowing startup to complete and the witness inspector to run and report.

4. **Item 4 — Inspector / Build Witness-Address Alignment (`candidate_port2a/` @ `0x0035F7A0`)** `[VERIFIED: host binding; UNKNOWN: camera readout]`:
   - **Status / Classification**: **`NEEDED_FOR_FIRST_BOOT`** `[VERIFIED: host binding; UNKNOWN: camera readout]`, **not ROM-closable**.
   - **Citations**: `tools/build_candidate_port2a.py:651-701, 830-833`; `docs/PORT16_CANDIDATE_BUILD.md:26`; `firmware/tools/witness_inspector_payload.S:57-93`; `docs/PORT16_WITNESS_ADDRESS.md:14-29`.
   - **Host-Side Binding Completed and Verified**: The host-side binding is completed and verified `[VERIFIED: tools/build_candidate_port2a.py:651-701, 830-833; docs/PORT16_CANDIDATE_BUILD.md:26]`. The candidate builder `tools/build_candidate_port2a.py:651-701, 830-833` generates and validates the aligned inspector payload (`candidate_port2a/witness_inspector_payload.bin`) and metadata (`candidate_port2a/witness_inspector_metadata.json`) targeted to `boot_witness` at `0x0035F7A0` strictly within the build output directory `candidate_port2a/`, without modifying historical artifacts under `firmware/tools/` (`docs/PORT16_CANDIDATE_BUILD.md:26`).
   - **Reason Not ROM-Closable**: Host-side build and toolchain configuration item, not a static ROM unknown. Reading static ROM bytes cannot configure host build tooling or compile inspector binaries.
   - **Proposed observation for the owner trial plan `[INFERRED]`**: The owner deploys the aligned candidate build and inspector artifacts from `candidate_port2a/` to the SD card, executes `firmware/tools/witness_inspector_gm110c.m` on camera, and verifies that the inspector reads the witness structure at `0x0035F7A0` without reporting `ERR_READ` or invalid witness data (`firmware/tools/witness_inspector_payload.S:60-93`).

5. **Item 5 — Dual-Flag Boot Marker Coexistence and Post-Boot Script Activation** `[INFERRED]`:
   - **Status / Classification**: **`NEEDED_FOR_FIRST_BOOT`** `[INFERRED]`, **not ROM-closable** (Status: `UNKNOWN`) `[UNKNOWN]`.
   - **Citations**: `docs/HANDOFF.md:435, 463; docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:33; docs/CANON_BASIC_ACTIVATION_INVESTIGATION.md:20-25`.
   - **Reason Not ROM-Closable**: Coexistence of volume boot record (VBR) markers (`BOOTDISK` at `0x1E0` and `SCRIPT` at `0x1F0`) and post-boot Canon Basic script triggering behavior depend on stock Canon bootloader interaction with physical SD card media formatting. This is a media formatting and bootloader interaction question, not a static ROM unknown.
   - **Proposed observation for the owner trial plan `[INFERRED]`**: The owner prepares an SD card with dual markers (`BOOTDISK` at offset `0x1E0` and `SCRIPT` at `0x1F0`), boots the camera, and verifies that `DISKBOOT.BIN` is loaded and executed, followed by successful execution of the Canon Basic script (`firmware/tools/witness_inspector_gm110c.m`) on the camera.

6. **Item 6 — Current-Attempt Witness Freshness Verification** `[UNKNOWN]`:
   - **Status / Classification**: **`NEEDED_FOR_FIRST_BOOT`** `[UNKNOWN]`, **not ROM-closable**.
   - **Citations**: `tools/build_candidate_port2a.py:783`; `firmware/tools/witness_inspector_payload.S:96-113, 165-174`; `firmware/tools/witness_inspector_gm110c.m:28`; `docs/HANDOFF.md:430, 466`.
   - **Reason Not ROM-Closable**: Candidate build configuration records a fixed nonce `0x32A80001` (`tools/build_candidate_port2a.py:783`). Inspector payload logic explicitly excludes that constant from the freshness proof (`firmware/tools/witness_inspector_payload.S:96-113`), noting that constant nonce `0x32A80001` is never considered freshness proof and proceeds to stage checks without confirming freshness. In the offline prototype script, `expected_nonce = 0` produces `FRESHNESS_UNVERIFIED` (`firmware/tools/witness_inspector_gm110c.m:28; firmware/tools/witness_inspector_payload.S:165-174`). Supplying a different or dynamic expected nonce does not close freshness: a dynamic challenge would need an independently established producer-side mechanism (such as the boot stub generating and recording a fresh unpredictable nonce per boot attempt), and no such producer-side mechanism exists in the documented candidate. This protocol and architecture gap cannot be settled by reading static ROM bytes.
   - **Proposed observation for the owner trial plan `[INFERRED]`**: Supplying a different or dynamic expected nonce does not close freshness. The item remains `[UNKNOWN]` until an independently established producer-side dynamic nonce mechanism, or an independently verified DRAM memory-transition observation (e.g. verified DRAM pattern decay across a cold power cycle before candidate boot), exists.

7. **Item 7 — Operational Mode Transition to Shooting Live View** `[INFERRED]`:
   - **Status / Classification**: **`NEEDED_FOR_FIRST_BOOT`** `[INFERRED]`, **not ROM-closable** (Status: `UNKNOWN`) `[UNKNOWN]`.
   - **Citations**: `firmware/tools/witness_inspector_gm110c.m:185-188; docs/HANDOFF.md:1439`.
   - **Reason Not ROM-Closable**: Retained message descriptors (`h_title`, `h_status`) allocated by the inspector in Playback mode render on the camera LCD only upon transitioning the physical camera into Shooting Live View (`firmware/tools/witness_inspector_gm110c.m:185-188; docs/HANDOFF.md:1439`). This is a physical camera UI operational procedure, not a static ROM unknown.
   - **Proposed observation for the owner trial plan `[INFERRED]`**: The owner operates the physical camera mode switch or half-presses the shutter button to transition from Playback mode into Shooting Live View and visually observes the two retained message lines rendered on the LCD screen (`firmware/tools/witness_inspector_gm110c.m:185-188; docs/HANDOFF.md:1439`).

8. **Item 8 — Stock `task_InitFileModules` Dispatch and Normal Completion (`U2(d)-stock`, `OBLIG-U2-02`, `OBLIG-U2-03`)** `[UNKNOWN]`:
   - **Status / Classification**: **`NEEDED_FOR_FIRST_BOOT`** `[UNKNOWN]`, **not ROM-closable**.
   - **Citations**: `tools/port13_u2_obligations.py:628-678`; `firmware/tools/witness_inspector_gm110c.m:100-121`.
   - **Reason Not ROM-Closable**: Whether the inspector's stock file reads depend on stock `task_InitFileModules` dispatch and normal completion cannot be shown from the cited source, and no cited boot-stub, build or inspector line shows first boot is independent of it. Both obligations are `kind=ObligationKind.RUNTIME` requiring an execution/completion witness in the current boot generation, and their notes state static ROM entry evidence cannot discharge them (`tools/port13_u2_obligations.py:634-637, 648, 659-662, 676`).
   - **Proposed observation for the owner trial plan `[INFERRED]`**: Closure is split into two distinct parts:
     - *(a) Functional first-boot observation*: In the same attempt, all three inspector file operations (open, read and close) succeed (`firmware/tools/witness_inspector_gm110c.m:100-121`). Reaching the stock UI alone does not establish this, because the inspector can abort on any failure (`firmware/tools/witness_inspector_gm110c.m:100-121`). This answers only the functional first-boot question (whether stock file reading functioned during the trial); label: functional first-boot observation `[INFERRED]`.
     - *(b) Discharge of the canonical obligations*: Discharging `OBLIG-U2-02` and `OBLIG-U2-03` requires the specific observations defined in `tools/port13_u2_obligations.py:628-678`: current-generation dynamic execution evidence confirming `task_InitFileModules` ran after DryOS scheduler dispatch in the active boot generation context (`:630-642`), and current-generation completion evidence confirming both `sub_fc0d9ccc` and `sub_fc0d9cf6` returned normally without latched fault (`:654-668`).
     - *Separation and status*: Observation (a) does NOT discharge (b). Inspector file operations succeeding does not prove scheduler dispatch of `task_InitFileModules` or normal completion of `sub_fc0d9ccc` / `sub_fc0d9cf6`. Therefore, `OBLIG-U2-02` and `OBLIG-U2-03` stay `[UNKNOWN]` after a successful first boot unless (b) is specifically observed.

---

### 4.3 Summary of Evidence Requirements Across Open Items

Across all eight open needed items:
1. **Zero Static ROM Ranges Required**: Exactly **0 ROM ranges** are needed or proposed (0 bytes total, within the 4096 B budget). None of the open items can be closed by reading static ROM bytes:
   - Items 1, 2, 3 and 8 (`U2(c)`, `U4(b)(ii)`, `U4(c)`, `U2(d)-stock`) are dynamic runtime hardware/RTOS/stock-initialisation questions governed by runtime obligations (`OBLIG-U2-08`, `OBLIG-U2-02`, `OBLIG-U2-03` declared `kind=ObligationKind.RUNTIME` at `tools/port13_u2_obligations.py:634, 659, 788`; `OBLIG-U4-09`, `OBLIG-U4-11` declared `requires_runtime_evidence=True` at `tools/port13_oblig_u4.py:308, 340`) `[VERIFIED]`.
   - Item 4 (Witness Address Alignment) is a host-side metadata and build tooling binding completed in `candidate_port2a/` (`tools/build_candidate_port2a.py:651-701, 830-833; docs/PORT16_CANDIDATE_BUILD.md:26`) `[VERIFIED]`.
   - Items 5, 6, and 7 (Dual Markers, Freshness, Mode Transition) are media, anti-replay protocol, and physical operational dependencies (`tools/build_candidate_port2a.py:783`; `firmware/tools/witness_inspector_payload.S:96-113, 165-174`; `docs/HANDOFF.md:430, 435, 463, 466, 1439`) `[VERIFIED]`.
2. **Phase 0 Safety Gate Compliance**: Because zero ROM ranges are proposed, zero ROM reading, memory dumping, or hardware probing is performed in this task, strictly conforming to the read-only offline Phase 0 safety protocol (`docs/SAFETY.md:1-8`) `[VERIFIED]`.

---

### 4.4 Post-First-Boot Milestone Deferral

All unknown facets triaged as **`NOT_NEEDED_FOR_FIRST_BOOT`** in Sections 2 and 3:
- `U1` (DryOS `CreateTask` prologue bytes and replayed literal, `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:140; tools/port13_oblig_u4.py:184-198`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:358-366; tools/port9b_runtime_contract.py:453]`
- `U2(a)` (CHDK `InitFileModules` gate, replacement task, and latch synchronization, `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:141; tools/port13_u2_obligations.py:732-779`) `[VERIFIED: tools/port9b_runtime_contract.py:455-456]`
- `U2(b)` (Deferred CHDK filesystem assertions & mount state preconditions, `tools/port13_u2_obligations.py:680-730`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:27-29, 39, 52, 411-416]`
- `U2(d)-CHDK` (CHDK SpyTask-driven consumption of `InitFileModules` completion, `docs/PORT10A_RUNTIME_PRECONDITION_EVIDENCE.md:180-183`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:411-416; tools/port9b_runtime_contract.py:455-456]`
- `U3` (`task_PhySw` keyboard interception and routing, `docs/PORT9A_RUNTIME_INTEGRATION_MAP.md:142`) `[INFERRED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:409; tools/port9b_runtime_contract.py:454]`
- `U4(a)` (SpyTask launch site, priority, stack, gating, CPU mode, yield constraints, and timeout bypass, `tools/port13_oblig_u4.py:168-294, 310-325`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:411-416; tests/test_port9b_runtime_contract.py:86-89]`
- `U4(b)(i)` (Task-priority behaviour / RTOS scheduling policy, `tools/port13_oblig_u4.py:199-215`) `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:358-366, 411-416]`

are strictly required only for full CHDK runtime integration (enabling CHDK SpyTask, GUI console, script engine, RAW capture, and key handling) `[INFERRED]`. Under the Phase 0 safety policy, these items are formally deferred to subsequent milestones (PORT-17 and beyond) when production CHDK tasks are integrated and enabled `[INFERRED]`.

---

## 5. Verification and Compliance Summary

1. **Strict Read-Only Investigation (Phase 0 Policy)**: This document was produced under the strict Phase 0 read-only safety model (`docs/SAFETY.md:1-8`). Zero camera hardware trials, zero ROM dumping, zero firmware flashing, zero binary modifications, and zero script executions were performed `[VERIFIED: docs/SAFETY.md:1-8]`.
2. **First-Boot Scope Discipline**: All triage decisions strictly enforce the narrow first-boot boundary: first boot means only that `DISKBOOT.BIN` loads, the corrected boot stub in `chdk-port/platform/g3x/sub/110c/` runs, and the boot witness becomes observable to the owner through the witness inspector. It does NOT include filesystem flush or unmount integrity, lock ownership or task-priority behaviour, unless a cited line of the boot stub, the build or the inspector actually depends on them. All downstream features (CHDK SpyTask, GUI console, key routing, file writing, RAW capture) are strictly excluded from first-boot scope and deferred to post-first-boot milestones `[VERIFIED]`.
3. **No Tracked vs Untracked Evidence Blur**: Every evidentiary claim in this document is supported exclusively by Git-tracked repository files. Where earlier historical documents referenced untracked files (`docs/UI001C_DESIGN_REVIEW.md`, `docs/BOOT001A_HARDWARE_RESULT.md`, `docs/CHDK_PORT1F2_FINAL_EVIDENCE.md`), those claims are formally isolated in Section 1.2 and classified as `[UNKNOWN]` without being treated as evidence `[VERIFIED]`. All proposed owner-trial procedures are labeled `[INFERRED]` and designated as proposed observations for the owner trial plan `[VERIFIED]`.
4. **Verified File:Line Citations Across Tracked Artifacts**:
   - All 8 obligations in `tools/port13_u2_obligations.py` have their exact definition line ranges verified and cited: `OBLIG-U2-01` (`:599-625`), `OBLIG-U2-02` (`:628-649`), `OBLIG-U2-03` (`:652-678`), `OBLIG-U2-04` (`:680-704`), `OBLIG-U2-05` (`:706-730`), `OBLIG-U2-06` (`:732-754`), `OBLIG-U2-07` (`:757-779`), and `OBLIG-U2-08` (`:782-806`) `[VERIFIED: tools/port13_u2_obligations.py:599-806]`.
   - All 11 obligations in `tools/port13_oblig_u4.py` have their exact definition line ranges verified and cited: `OBLIG-U4-01` (`:168-183`), `OBLIG-U4-02` (`:184-198`), `OBLIG-U4-03` (`:199-215`), `OBLIG-U4-04` (`:216-231`), `OBLIG-U4-05` (`:232-247`), `OBLIG-U4-06` (`:248-262`), `OBLIG-U4-07` (`:263-278`), `OBLIG-U4-08` (`:279-294`), `OBLIG-U4-09` (`:295-309`), `OBLIG-U4-10` (`:310-325`), and `OBLIG-U4-11` (`:326-341`) `[VERIFIED: tools/port13_oblig_u4.py:168-341]`.
   - Corrected citations for `chdk-port/platform/g3x/sub/110c/boot_prototype.c` verified: CreateTask parameter block at lines 358-366 (veneer at line 365), PhySw at line 409, commented SpyTask at lines 411-416 (commented call at line 416), witness continuation recording at line 430, continuation tail branch at line 434 `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:358-436]`.
   - Inspector file operations verified in `firmware/tools/witness_inspector_gm110c.m`: `Fopen_Fut` at line 100, error check and abort at lines 101-105; `Fread_Fut` at line 109, size check and abort at lines 111-115; `Fclose_Fut` at line 110, close check and abort at lines 117-121 `[VERIFIED: firmware/tools/witness_inspector_gm110c.m:100-121]`.
   - Builder alignment implementation verified in `tools/build_candidate_port2a.py:651-701, 830-833` generating aligned inspector inside `candidate_port2a/` without modifying `firmware/tools/`, and confirmed in `docs/PORT16_CANDIDATE_BUILD.md:26` `[VERIFIED: tools/build_candidate_port2a.py:651-701, 830-833; docs/PORT16_CANDIDATE_BUILD.md:26]`.
   - Nonce and freshness implementation verified in candidate and inspector: `tools/build_candidate_port2a.py:783` records fixed nonce `0x32A80001`, and `firmware/tools/witness_inspector_payload.S:96-113` explicitly excludes constant nonce `0x32A80001` from the freshness proof, requiring an independently established producer-side dynamic challenge mechanism (which does not exist in the candidate) `[VERIFIED: tools/build_candidate_port2a.py:783; firmware/tools/witness_inspector_payload.S:96-113]`.
5. **Accurate Description of Kernel Init Calling Convention**: Lines 231-232 clear `sp[0x38] = 0`, line 240 loads the callback into register `r1 = sub_fc05b558_my`, line 251 sets `r0 = sp`, and line 252 dispatches into kernel initialization `blx sub_fc31b408` with `(r0=sp, r1=sub_fc05b558_my)` `[VERIFIED: chdk-port/platform/g3x/sub/110c/boot_prototype.c:231-232, 240, 251-252]`.
6. **Inclusion of Inspector / Build Witness-Address Dependency**: Section 4.2 includes the witness-address alignment (`candidate_port2a/` @ `0x0035F7A0`), describing host-side binding as completed and verified (`tools/build_candidate_port2a.py:651-701, 830-833; docs/PORT16_CANDIDATE_BUILD.md:26`), with camera observation staying `[UNKNOWN]` until the owner trial, explicitly noting that 0 ROM ranges are proposed because it is a host-side build binding marked 'not ROM-closable' `[VERIFIED: tools/build_candidate_port2a.py:651-701, 830-833; docs/PORT16_CANDIDATE_BUILD.md:26]`.
7. **Explicit Triage of U2 Categories & OBLIG-U2-08**:
   - Category (i) (`U2(a)`, `U2(b)`, `U2(d)-CHDK`: CHDK readiness gate/latch `OBLIG-U2-06/07`, CHDK filesystem assertions `OBLIG-U2-04/05`, CHDK SpyTask-driven consumption of completion per `docs/PORT10A_RUNTIME_PRECONDITION_EVIDENCE.md:180-183`) is triaged as `NOT_NEEDED_FOR_FIRST_BOOT` with citations `[VERIFIED: source; INFERRED: path]`. No tracked U2 obligation defines CHDK flush/unmount or lock use, so none is triaged.
   - Category (ii) / Facet `U2(c)` (stock SD read capability for inspector and warm-restart SD re-enumeration without bus lockup, `OBLIG-U2-08` at `tools/port13_u2_obligations.py:782-806`, `firmware/tools/witness_inspector_gm110c.m:100-121`) is triaged as `NEEDED_FOR_FIRST_BOOT`, labeled `[UNKNOWN]`, marked 'not ROM-closable' with 0 B ROM ranges, and closed when inspector file open, read and close succeed in the current attempt `[UNKNOWN]`.
   - Category (ii) / Facet `U2(d)-stock` (stock `task_InitFileModules` dispatch and normal completion, `OBLIG-U2-02/03` at `tools/port13_u2_obligations.py:628-678`) is triaged as `NEEDED_FOR_FIRST_BOOT`, labeled `[UNKNOWN]`, explicitly noting that the absence of CHDK operations is not evidence that stock reads do not depend on stock initialisation, marked 'not ROM-closable' with 0 B ROM ranges. Closure is split into (a) functional first-boot observation (all three inspector file operations—open, read, and close—succeed in the same attempt; reaching stock UI alone does not establish this as the inspector can abort on any failure per `firmware/tools/witness_inspector_gm110c.m:100-121`), which answers only the first-boot question, and (b) canonical obligation discharge, which requires current-generation execution evidence for `task_InitFileModules` and completion evidence for `sub_fc0d9ccc` / `sub_fc0d9cf6` per `tools/port13_u2_obligations.py:628-678`. Observation (a) does not discharge (b), and `OBLIG-U2-02/03` stay `[UNKNOWN]` after a successful first boot unless (b) is observed `[UNKNOWN]`.
   - Each `OBLIG-U2-0x` ID appears under exactly one decision: `-02/-03` → U2(d)-stock (NEEDED); `-04/-05` → U2(b) (NOT_NEEDED); `-06/-07` → U2(a) (NOT_NEEDED); `-08` → U2(c) (NEEDED); `-01` is STATIC/VERIFIED and needs no triage (`tools/port13_u2_obligations.py:606-607`) `[VERIFIED]`.
8. **Explicit Triage of U4 Continuation Safety & Warm Restart**:
   - `U4(b)` is split into (i) priority policy (`OBLIG-U4-03`), `NOT_NEEDED_FOR_FIRST_BOOT` `[VERIFIED: source; INFERRED: path]`, and (ii) continuation safety after tail branch `b.w sub_fc0d0126` (`OBLIG-U4-09`, `tools/port13_oblig_u4.py:295-309`), `NEEDED_FOR_FIRST_BOOT`, labeled `[UNKNOWN]`, marked 'not ROM-closable' with 0 B ROM ranges, closed when camera keeps starting after stub branch and inspector runs and reports `[UNKNOWN]`.
   - `U4(c)` (warm-restart semaphores / kernel re-init teardown, `OBLIG-U4-11`, `tools/port13_oblig_u4.py:326-341`) removes the clean cold-start premise, citing `docs/RESTART_SD_HOST_AUDIT.md:11-29` and `docs/CODEX_INDEPENDENT_RESTART_REVIEW.md:80-82`, decided `NEEDED_FOR_FIRST_BOOT`, labeled `[UNKNOWN]`, marked 'not ROM-closable' with 0 B ROM ranges, closed when camera completes kernel init without semaphore freeze and inspector runs and reports `[UNKNOWN]`.
9. **Zero ROM Bytes Read or Quoted**: Exactly zero ROM bytes, hex opcodes, instruction encodings, opcode words, or binary dumps were accessed or quoted in this document `[VERIFIED]`. All findings from prior tasks are summarized in words and cite tracked repository artifacts `[VERIFIED]`.
10. **Zero Address Inferences**: Every ROM address cited in this document carries an explicit citation to a tracked repository artifact (`0xFC31BBC4` at `docs/PORT11A_GM110C_ROM_EVIDENCE.md:61`; `0xFC0BD070` at `docs/PORT11A_GM110C_ROM_EVIDENCE.md:65`; `0xFC1283D2` at `docs/PORT11A_GM110C_ROM_EVIDENCE.md:67`; `0xFC0D0126` at `docs/CHDK_PORT1C1_CRITICAL_AUDIT.md:22`) `[VERIFIED]`. No addresses are guessed or inferred without evidence `[VERIFIED]`.
11. **Strict Sizing & Scope Compliance**: Exactly 0 ROM ranges are proposed (<= 4096 B total, <= 512 B per range), all 8 open needed items are explicitly marked 'not ROM-closable' with reason, UNKNOWN label (or host binding VERIFIED / camera readout UNKNOWN for witness address), and proposed owner-trial observation, all U1–U4 unknowns (including U2(a)–(c), U2(d)-stock, U2(d)-CHDK and U4(a)–(c)) are triaged with exact file:line citations under the narrow first-boot definition, a summary table is placed at the top before any detailed discussion, and only `docs/PORT16_FIRSTBOOT_U_TRIAGE.md` is modified `[VERIFIED]`.
