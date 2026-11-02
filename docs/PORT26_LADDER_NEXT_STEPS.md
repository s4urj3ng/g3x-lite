# PORT-26 T2b: Per-Class Next-Step Triage Plan (GM1.10C)

This plan enumerates every code class defined in `tools/port26_ladder_decode.py:LADDER_STAGE_TABLE` (29 codes) and specifies the stage transition, intervening execution, likely power-off/wait point, and next candidate action `[VERIFIED: tools/port26_ladder_decode.py:161-516]`.

### Code 1: STAGE_LOADER_AFTER_PROLOGUE (`CODE_1`)
(a) Stage reached -> next stage: `STAGE_LOADER_AFTER_PROLOGUE` -> `STAGE_LOADER_AFTER_COPY` (emitted via `tools/build_candidate_port25_ladder_fix.py:67, 337-340`; `chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:45`; `boot_prototype.c` not yet entered).
(b) Execution: `loader_main_breadcrumb.c:54-96`: pointer setup, `core_copy(src, dst, word_len)` relocating 116,816 B to `0x003489B4`, and boot witness Stage 1 write to `0x0035F7A0`.
(c) Likely power-off/wait point: Autonomous PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN: external microcontroller firmware]`, or RAM relocation stall `[UNKNOWN]`.
Next candidate change: [INFERRED] Add finer LED breadcrumb immediately before core_copy() (chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:61; docs/PORT23_LED_BREADCRUMBS.md:46).

### Code 2: STAGE_LOADER_AFTER_COPY (`CODE_2`)
(a) Stage reached -> next stage: `STAGE_LOADER_AFTER_COPY` -> `STAGE_LOADER_BEFORE_DCACHE` (emitted via `tools/build_candidate_port25_ladder_fix.py:67, 337-340`; `chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:99`; `boot_prototype.c` not yet entered).
(b) Execution: `loader_main_breadcrumb.c:100-117`: inline asm prologue loading `r0 = %0` (`0x003489B4`), `r1 = %1` (size), `r2 = %2` (`ROM_DCACHE_CLEAN_INV`). Adjacent breadcrumb emission/timing only.
(c) Likely power-off/wait point: Autonomous PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN: external microcontroller firmware]`.
Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of sub-CPU autonomous latch timeout protocol (docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216).

### Code 3: STAGE_LOADER_BEFORE_DCACHE (`CODE_3`)
(a) Stage reached -> next stage: `STAGE_LOADER_BEFORE_DCACHE` -> `STAGE_LOADER_AFTER_DCACHE` (emitted via `tools/build_candidate_port25_ladder_fix.py:67, 337-340`; `chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:116`; `boot_prototype.c` not yet entered).
(b) Execution: `loader_main_breadcrumb.c:118-125`: `mov r0, %0; mov r1, %1; ldr r2, =%2; blx r2` calling `ROM_DCACHE_CLEAN_INV` (`0xFC127AB1`), followed by `dsb sy` (`PORT25-ROM-CACHE-MAINT`).
(c) Likely power-off/wait point: Exception/hang during `ROM_DCACHE_CLEAN_INV` (`0xFC127AB1`, `PORT25-ROM-CACHE-MAINT`) or PMIC latch timeout (`docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of ROM_DCACHE_CLEAN_INV subroutine at 0xFC127AB1 (PORT25-ROM-CACHE-MAINT; docs/PORT25_SHORT_PRESS_LOCALISE.md:397).

### Code 4: STAGE_LOADER_AFTER_DCACHE (`CODE_4`)
(a) Stage reached -> next stage: `STAGE_LOADER_AFTER_DCACHE` -> `STAGE_LOADER_BEFORE_ICACHE` (emitted via `tools/build_candidate_port25_ladder_fix.py:67, 337-340`; `chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:127`; `boot_prototype.c` not yet entered).
(b) Execution: `loader_main_breadcrumb.c:126-133`: adjacent breadcrumb macros with no intervening instructions; interval is breadcrumb emission/timing only.
(c) Likely power-off/wait point: Breadcrumb emission timing delay or PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of PMIC power latch hold timing (docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216).

### Code 5: STAGE_LOADER_BEFORE_ICACHE (`CODE_5`)
(a) Stage reached -> next stage: `STAGE_LOADER_BEFORE_ICACHE` -> `STAGE_LOADER_AFTER_ICACHE` (emitted via `tools/build_candidate_port25_ladder_fix.py:67, 337-340`; `chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:132`; `boot_prototype.c` not yet entered).
(b) Execution: `loader_main_breadcrumb.c:135-142`: `mov r0, %0; mov r1, %1; ldr r2, =%3; blx r2` calling `ROM_ICACHE_INV_BP` (`0xFC127B09`), followed by `dsb sy` and `isb sy` (`PORT25-ROM-CACHE-MAINT`).
(c) Likely power-off/wait point: Exception/hang during `ROM_ICACHE_INV_BP` (`0xFC127B09`, `PORT25-ROM-CACHE-MAINT`) or PMIC latch timeout (`docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of ROM_ICACHE_INV_BP subroutine at 0xFC127B09 (PORT25-ROM-CACHE-MAINT; docs/PORT25_SHORT_PRESS_LOCALISE.md:397).

### Code 6: STAGE_LOADER_AFTER_ICACHE (`CODE_6`)
(a) Stage reached -> next stage: `STAGE_LOADER_AFTER_ICACHE` -> `STAGE_LOADER_BEFORE_BX` (emitted via `tools/build_candidate_port25_ladder_fix.py:67, 337-340`; `chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:144`; `boot_prototype.c` not yet entered).
(b) Execution: `loader_main_breadcrumb.c:148`: `cpsid if` enforcing disabled interrupt state prior to handoff.
(c) Likely power-off/wait point: Hardware fault during CPSID or PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of CPU mode and interrupt state at loader handoff (docs/RESTART_IRQ_PENDING_AUDIT.md:1-50; docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216).

### Code 7: STAGE_LOADER_BEFORE_BX (`CODE_7`)
(a) Stage reached -> next stage: `STAGE_LOADER_BEFORE_BX` -> `STAGE_BC_CORE_ENTRY` (emitted via `tools/build_candidate_port25_ladder_fix.py:67, 337-340`; `loader_main_breadcrumb.c:152`; enters `boot_prototype.c:85-91` at Code 11).
(b) Execution: `loader_main_breadcrumb.c:170-173`: terminal `bx r0` to `MEMISOSTART` (`0x003489B5`); entry into relocated `boot()` at `boot_prototype.c:85-91`: `movw r0, #0x4000; movt r0, #0; mov sp, r0`.
(c) Likely power-off/wait point: Branch fault transitioning to relocated memory or PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
Next candidate change: [INFERRED] Add finer LED breadcrumb immediately before bx r0 in loader_entry_breadcrumb.S or at entry of boot() (chdk-port/platform/g3x/sub/110c/boot_prototype.c:85; docs/PORT23_LED_BREADCRUMBS.md:50).

### Code 11: STAGE_BC_CORE_ENTRY (`CODE_11`)
(a) Stage reached -> next stage: `STAGE_BC_CORE_ENTRY` -> `STAGE_BC_POST_BSS` (emitted in `tools/build_candidate_port25_ladder_fix.py:110` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:91`).
(b) Execution: `boot_prototype.c:98-154`: `bl sub_fc02007e` (copy exception vectors, `PORT25-ROM-BOOT-EARLY`), `*(0xC0242010) |= 1`, Copy Loop 1 (High RAM), `sub_fc127a62`, Copy Loop 2 (ATCM), Copy Loop 3 (Low RAM `0x00008000..0x0003F4F4`), and Canon BSS zeroing `loc_zero_bss` (`0x0003F4F4..0x003489B4`).
(c) Likely power-off/wait point: Bus error during RAM copy loops or PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
Next candidate change: [INFERRED] Add finer LED breadcrumb between sub_fc02007e vector copy and High RAM copy loop (chdk-port/platform/g3x/sub/110c/boot_prototype.c:99-106; docs/PORT25_SHORT_PRESS_LOCALISE.md:68-70).

### Code 12: STAGE_BC_POST_BSS (`CODE_12`)
(a) Stage reached -> next stage: `STAGE_BC_POST_BSS` -> `STAGE_BC_STAGE3_ENTRY` (emitted in `tools/build_candidate_port25_ladder_fix.py:111` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:153-154`).
(b) Execution: `boot_prototype.c:159-174`: branch `b.w sub_fc05b3c8_my` (line 159), entry to `sub_fc05b3c8_my` (`push {r4, lr}` at line 171), and call `bl witness_record_core` at line 174.
(c) Likely power-off/wait point: Branch failure or witness record crash in `sub_fc05b3c8_my` (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
Next candidate change: [INFERRED] Add finer LED breadcrumb immediately before witness_record_core (chdk-port/platform/g3x/sub/110c/boot_prototype.c:171-174; docs/PORT25_SHORT_PRESS_LOCALISE.md:76-77).

### Code 13: STAGE_BC_STAGE3_ENTRY (`CODE_13`)
(a) Stage reached -> next stage: `STAGE_BC_STAGE3_ENTRY` -> `STAGE_BC_PRE_KERNEL_INIT` (emitted in `tools/build_candidate_port25_ladder_fix.py:112` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:174-175`).
(b) Execution: `boot_prototype.c:177-255`: load `new_sa` into `r4`, headroom calculation against `0x006CE000` (lines 184-188), setup Low RAM bounds at `0x00008074..0x0000807C` (lines 196-203), memset setup struct via `sub_fc31bfac`, DryOS memory descriptor setup (lines 212-250), continuation callback pointer setup `ldr r1, =sub_fc05b558_my` (line 244).
(c) Likely power-off/wait point: Headroom check verified to pass (Candidate 8, `docs/PORT25_SHORT_PRESS_LOCALISE.md:298-303; PORT25-ROM-HEAP-SETUP`), so it is not the cause. Likely cause is autonomous PMIC latch timeout (Candidate 2 / Rank 4, lines 200-216) `[UNKNOWN: external microcontroller firmware]`.
Next candidate change: [INFERRED] Add finer LED breadcrumb immediately after Low RAM bounds setup (chdk-port/platform/g3x/sub/110c/boot_prototype.c:203; docs/PORT25_SHORT_PRESS_LOCALISE.md:79).

### Code 14: STAGE_BC_PRE_KERNEL_INIT (`CODE_14`)
(a) Stage reached -> next stage: `STAGE_BC_PRE_KERNEL_INIT` -> `STAGE_BC_STAGE4_ENTRY` (emitted in `tools/build_candidate_port25_ladder_fix.py:113` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:255-256`).
(b) Execution: `boot_prototype.c:255-271`: `mov r0, sp; blx sub_fc31b408` (DryOS kernel init, `PORT25-ROM-KERNEL-INIT-VENEER`), DryOS task scheduler initialization, dispatch of Initial Task `sub_fc05b558_my` (lines 244, 268), and entry `push {r4, lr}` (line 271).
(c) Likely power-off/wait point: Hang or interrupt re-enable stall in DryOS kernel init `sub_fc31b408` (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216, 252-256; PORT25-ROM-KERNEL-INIT-VENEER`) `[UNKNOWN]`.
Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of DryOS kernel initialization sub_fc31b408 and ATCM 0xBFE10F79 (PORT25-ROM-KERNEL-INIT-VENEER; docs/PORT25_SHORT_PRESS_LOCALISE.md:251-256).

### Code 15: STAGE_BC_STAGE4_ENTRY (`CODE_15`)
(a) Stage reached -> next stage: `STAGE_BC_STAGE4_ENTRY` -> `STAGE_BC_STAGE5_ENTRY` (emitted in `tools/build_candidate_port25_ladder_fix.py:114` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:271-272`).
(b) Execution: `boot_prototype.c:272-335`: Stage 4 subsystem setup: USER_MEM check, `dmSetup` (`sub_fc418738`), `termDriverInit` (`sub_fc05c7d4`), `termDeviceCreate` (`sub_fc05c862`), `stdioSetup` (`sub_fc05b794`), `stdlibSetup` (`sub_fc05b8d8`), `extlib_setup` (`sub_fc05e910`), error checks branching to `sub_fc05b5ea` (`PORT25-ROM-INIT-TASK`), and tail branch `b.w sub_fc05b962_my` (line 334).
(c) Likely power-off/wait point: Subsystem setup error branching to `sub_fc05b5ea` (Candidate 7 / Rank 7, `docs/PORT25_SHORT_PRESS_LOCALISE.md:278-292; PORT25-ROM-INIT-TASK`), or PMIC latch timeout (Candidate 2 / Rank 4, lines 200-216) `[UNKNOWN]`.
Next candidate change: [INFERRED] Add finer LED breadcrumb immediately after termDeviceCreate (chdk-port/platform/g3x/sub/110c/boot_prototype.c:306-311; docs/PORT25_SHORT_PRESS_LOCALISE.md:306-311).

### Code 21: STAGE_BC_STAGE5_ENTRY (`CODE_21`)
(a) Stage reached -> next stage: `STAGE_BC_STAGE5_ENTRY` -> `STAGE_BC_PRE_MPU_SETUP` (emitted in `tools/build_candidate_port25_ladder_fix.py:115` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:344-345`).
(b) Execution: `boot_prototype.c:345-346`: `push {r3, lr}` preparing call to `bl sub_fc05ba68`; adjacent breadcrumbs with breadcrumb emission/timing interval only.
(c) Likely power-off/wait point: Breadcrumb emission delay or autonomous PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of PMIC autonomous latch timeout timing (docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216).

### Code 22: STAGE_BC_PRE_MPU_SETUP (`CODE_22`)
(a) Stage reached -> next stage: `STAGE_BC_PRE_MPU_SETUP` -> `STAGE_BC_POST_MPU_SETUP` (emitted in `tools/build_candidate_port25_ladder_fix.py:116` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:346`).
(b) Execution: `boot_prototype.c:346`: call `bl sub_fc05ba68` (`PORT25-ROM-STARTUP-TASKS`), executing `pxSetup` (`0xFC05BA6E`), `dhcpc_setup` (`0xFC05BA82`), and MPU configuration `mpuSetup` (`0xFC135280`, `PORT25-ROM-MPU-CONFIG`).
(c) Likely power-off/wait point: Setup failure in `pxSetup` or `dhcpc_setup` branching to `sub_fc05ba8e` (Candidate 7 / Rank 7, `docs/PORT25_SHORT_PRESS_LOCALISE.md:282-286; PORT25-ROM-STARTUP-TASKS`), or PMIC latch timeout (Candidate 2 / Rank 4, lines 200-216) `[UNKNOWN]`.
Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of Stage 5 error handler sub_fc05ba8e at 0xFC05BA8E (PORT25-ROM-STARTUP-TASKS; docs/PORT25_SHORT_PRESS_LOCALISE.md:133-136, 284-286).

### Code 23: STAGE_BC_POST_MPU_SETUP (`CODE_23`)
(a) Stage reached -> next stage: `STAGE_BC_POST_MPU_SETUP` -> `STAGE_BC_PRE_POWER_CHECK` (emitted in `tools/build_candidate_port25_ladder_fix.py:116` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:346-347`).
(b) Execution: `boot_prototype.c:347`: `bl sub_fc079404` (`IsNormalCameraMode_FW` reading pointer `0xFDF20380`, `PORT25-ROM-NORMAL-MODE; PORT25-ROM-NORMAL-FLAG`).
(c) Likely power-off/wait point: Crash in `sub_fc079404` or PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
Next candidate change: [INFERRED] Add finer LED breadcrumb immediately before sub_fc079404 (chdk-port/platform/g3x/sub/110c/boot_prototype.c:347; docs/PORT25_SHORT_PRESS_LOCALISE.md:141-143).

### Code 24: STAGE_BC_PRE_POWER_CHECK (`CODE_24`)
(a) Stage reached -> next stage: `STAGE_BC_PRE_POWER_CHECK` -> `STAGE_BC_POWER_CHECK_PASS` (emitted in `tools/build_candidate_port25_ladder_fix.py:117` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:347-348`).
(b) Execution: `boot_prototype.c:348-358`: call `bl sub_fc1284ac` sampling buttons (`PORT25-ROM-POWERON-CHECK`); under `G3X_POWERON_FIX=1` (`boot_prototype.c:349`), forces `movs r0, #1; b loc_fc05b978` jumping past power cut `sub_fc05ba56` to label `loc_fc05b978`.
(c) Likely power-off/wait point: In default build, button released causes `cbnz` fallthrough and GPIO 0x67 power cut in `sub_fc05ba56` (Candidate 1 / Rank 1, `docs/PORT25_SHORT_PRESS_LOCALISE.md:183-197; PORT25-ROM-STARTUP-TASKS; PORT25-ROM-GPIO-WRITE-MMIO`). In opt-in fix, unwritten startup cause `*(0x00009BD0)` from skipped `sub_fc08ecbc` (Candidate 4 / Rank 2, lines 234-246; `PORT25-ROM-STARTCAUSE-SAVE`) `[INFERRED]`.
Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of GPIO 0x67 power latch assert mechanism and value (PORT25-ROM-GPIO-WRITE-MMIO; docs/PORT25_SHORT_PRESS_LOCALISE.md:194-215).

### Code 25: STAGE_BC_POWER_CHECK_PASS (`CODE_25`)
(a) Stage reached -> next stage: `STAGE_BC_POWER_CHECK_PASS` -> `STAGE_BC_PRE_CREATE_STARTUP` (emitted in `tools/build_candidate_port25_ladder_fix.py:105` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:358-361`).
(b) Execution: `boot_prototype.c:359-369`: `blx sub_fc31b460`, `ldr r1, =0x006ce000; movs r0, #0; bl sub_fc382c8c` (ARAM heap init, `PORT25-ROM-ARAM-HEAP-INIT`), task argument setup (`movs r3, #0; str r3, [sp]; ldr r3, =task_Startup_my; movs r2, #0; movs r1, #0x19; ldr r0, =0xfc05b9a0`).
(c) Likely power-off/wait point: Allocation error or stall in ARAM heap init `sub_fc382c8c` (`PORT25-ROM-ARAM-HEAP-INIT`), or PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
Next candidate change: [INFERRED] Add finer LED breadcrumb immediately after sub_fc382c8c ARAM heap init (chdk-port/platform/g3x/sub/110c/boot_prototype.c:362; docs/PORT25_SHORT_PRESS_LOCALISE.md:342, 407).

### Code 26: STAGE_BC_PRE_CREATE_STARTUP (`CODE_26`)
(a) Stage reached -> next stage: `STAGE_BC_PRE_CREATE_STARTUP` -> `STAGE_BC_STARTUP_ENTRY` (emitted in `tools/build_candidate_port25_ladder_fix.py:119` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:369-373`).
(b) Execution: `boot_prototype.c:370-384`: `blx sub_fc31bbc4` (DryOS CreateTask veneer spawning "Startup", `PORT25-ROM-CREATETASK-VENEER`), `movs r0, #0; pop {r3, pc}` exiting Initial Task, DryOS task switch, and entry to `task_Startup_my` (`push {r4, lr}` at lines 381-384).
(c) Likely power-off/wait point: Task creation failure in `sub_fc31bbc4` (`PORT25-ROM-CREATETASK-VENEER`) or scheduler dispatch delay (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of DryOS task creation veneer sub_fc31bbc4 and scheduler queue (PORT25-ROM-CREATETASK-VENEER; docs/PORT25_SHORT_PRESS_LOCALISE.md:366-370).

### Code 28: STAGE_BC_FAIL_POWER_CUT (`CODE_28`)
(a) Stage reached -> next stage: `STAGE_BC_FAIL_POWER_CUT` -> `STAGE_BC_HALT_SHUTDOWN` (emitted in `tools/build_candidate_port25_ladder_fix.py:101` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:354`).
(b) Execution: `boot_prototype.c:354-356`: call `bl sub_fc05ba56` (`PORT25-ROM-STARTUP-TASKS`), which writes `0x004C0003` to GPIO 0x67 (`0xD20B099C`, `PORT25-ROM-GPIO-WRITE-MMIO`) cutting system power, reaching label `loc_fc05b976`.
(c) Likely power-off/wait point: Native button check failure de-asserting GPIO 0x67 power latch in `sub_fc05ba56` (Candidate 1 / Rank 1, `docs/PORT25_SHORT_PRESS_LOCALISE.md:183-197; PORT25-ROM-STARTUP-TASKS; PORT25-ROM-GPIO-WRITE-MMIO`).
Next candidate change: [VERIFIED] Enable G3X_POWERON_FIX=1 to bypass sub_fc05ba56 power-cut branch (chdk-port/platform/g3x/sub/110c/boot_prototype.c:348-355; docs/PORT24_POWERON_FIX.md:19-24; docs/PORT25_SHORT_PRESS_LOCALISE.md:152-155).

### Code 29: STAGE_BC_HALT_SHUTDOWN (`CODE_29`)
(a) Stage reached -> next stage: `STAGE_BC_HALT_SHUTDOWN` -> None (emitted in `tools/build_candidate_port25_ladder_fix.py:102` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:356-358`).
(b) Execution: `boot_prototype.c:357`: infinite branch loop `b loc_fc05b976` waiting for hardware power collapse following GPIO 0x67 de-assertion.
(c) Likely power-off/wait point: Post-cut spin loop following GPIO 0x67 power cut (Candidate 1 / Rank 1, `docs/PORT25_SHORT_PRESS_LOCALISE.md:194-197, 368; PORT25-ROM-STARTUP-TASKS`).
Next candidate change: [VERIFIED] Enable G3X_POWERON_FIX=1 to branch directly to loc_fc05b978 and bypass halt loop (chdk-port/platform/g3x/sub/110c/boot_prototype.c:348-355; docs/PORT24_POWERON_FIX.md:19-24; docs/PORT25_SHORT_PRESS_LOCALISE.md:152-155).

### Code 31: STAGE_BC_STARTUP_ENTRY (`CODE_31`)
(a) Stage reached -> next stage: `STAGE_BC_STARTUP_ENTRY` -> `STAGE_BC_POST_EARLY_INIT` (emitted in `tools/build_candidate_port25_ladder_fix.py:120` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:381-384`).
(b) Execution: `boot_prototype.c:384-388`: calls to early Canon driver subroutines: `bl sub_fc0d0150` (spawns "ClockSave", `PORT25-ROM-FIRMWARE-CONT`), `bl sub_fc05ba34`, `bl sub_fc05bb94`, and `bl sub_fc418eec` (`PORT25-ROM-STARTUP-TASKS`).
(c) Likely power-off/wait point: Crash or hang inside early driver routines `sub_fc0d0150..sub_fc418eec` (`PORT25-ROM-FIRMWARE-CONT; PORT25-ROM-STARTUP-TASKS`), or PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
Next candidate change: [INFERRED] Add finer LED breadcrumb immediately after sub_fc0d0150 ClockSave task creation (chdk-port/platform/g3x/sub/110c/boot_prototype.c:385; docs/PORT25_SHORT_PRESS_LOCALISE.md:164-166).

### Code 32: STAGE_BC_POST_EARLY_INIT (`CODE_32`)
(a) Stage reached -> next stage: `STAGE_BC_POST_EARLY_INIT` -> `STAGE_BC_PRE_SD1STINIT` (emitted in `tools/build_candidate_port25_ladder_fix.py:121` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:388-393`).
(b) Execution: `tools/build_candidate_port25_ladder_fix.py:121-122`, `chdk-port/platform/g3x/sub/110c/boot_prototype.c:389-397`: lines 390-396 contain comments only; Code 32 and Code 33 are adjacent breadcrumbs with no intervening calls or initializers. Interval is breadcrumb emission/timing only.
(c) Likely power-off/wait point: Breadcrumb emission timing delay or autonomous PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of PMIC autonomous latch timeout duration (docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216).

### Code 33: STAGE_BC_PRE_SD1STINIT (`CODE_33`)
(a) Stage reached -> next stage: `STAGE_BC_PRE_SD1STINIT` -> `STAGE_BC_POST_SD1STINIT` (emitted in `tools/build_candidate_port25_ladder_fix.py:122` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:397-402`).
(b) Execution: `boot_prototype.c:397-402`: `movs r0, #0; bl sub_fc05c4e0` querying card switch gate (`PORT25-ROM-CARD-SWITCHES`), `lsls r0, r0, #31; bne 1f`, and conditional task creation `blx sub_fc31b1f4` spawning "SD1stInit" (`PORT25-ROM-SD1STINIT-VENEER`).
(c) Likely power-off/wait point: SD card switch query fault in `sub_fc05c4e0` (`PORT25-ROM-CARD-SWITCHES`) or task spawn failure in `sub_fc31b1f4` (`PORT25-ROM-SD1STINIT-VENEER`), or PMIC latch timeout (`docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
Next candidate change: [INFERRED] Add finer LED breadcrumb immediately after sub_fc05c4e0 switch check (chdk-port/platform/g3x/sub/110c/boot_prototype.c:398; docs/PORT25_SHORT_PRESS_LOCALISE.md:390, 403).

### Code 34: STAGE_BC_POST_SD1STINIT (`CODE_34`)
(a) Stage reached -> next stage: `STAGE_BC_POST_SD1STINIT` -> `STAGE_BC_PRE_WATCHDOG_START` (emitted in `tools/build_candidate_port25_ladder_fix.py:123` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:402-407`).
(b) Execution: `boot_prototype.c:403-408`: sequential calls to driver routines: `bl sub_fc0bba02`, `bl sub_fc0d046c`, `bl sub_fc05bcdc`, and `bl sub_fc05bb24` (`PORT25-ROM-STARTDISKBOOT; PORT25-ROM-FIRMWARE-CONT`).
(c) Likely power-off/wait point: Crash or hang in driver setup calls `sub_fc0bba02..sub_fc05bb24`, or PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
Next candidate change: [INFERRED] Add finer LED breadcrumb immediately after sub_fc0d046c (chdk-port/platform/g3x/sub/110c/boot_prototype.c:405; docs/PORT25_SHORT_PRESS_LOCALISE.md:405).

### Code 35: STAGE_BC_PRE_WATCHDOG_START (`CODE_35`)
(a) Stage reached -> next stage: `STAGE_BC_PRE_WATCHDOG_START` -> `STAGE_BC_POST_WATCHDOG_START` (emitted in `tools/build_candidate_port25_ladder_fix.py:124` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:408`).
(b) Execution: `boot_prototype.c:408`: execution of `bl sub_fc418f2a` (`PORT25-ROM-WATCHDOG-START`), which configures and starts the hardware watchdog timer via `StartWDT_FW` (`0xFC135D2C`, `PORT25-ROM-WATCHDOG-MODULE`).
(c) Likely power-off/wait point: Hang inside watchdog start routine `sub_fc418f2a` (`PORT25-ROM-WATCHDOG-START; PORT25-ROM-WATCHDOG-MODULE`), or PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of StartWDT_FW MMIO registers at 0xFC135D2C and 0xD20A0000 (PORT25-ROM-WATCHDOG-MODULE; docs/PORT25_SHORT_PRESS_LOCALISE.md:221-226).

### Code 41: STAGE_BC_POST_WATCHDOG_START (`CODE_41`)
(a) Stage reached -> next stage: `STAGE_BC_POST_WATCHDOG_START` -> `STAGE_BC_PRE_PHYSW_CREATE` (emitted in `tools/build_candidate_port25_ladder_fix.py:124` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:408-413`).
(b) Execution: `boot_prototype.c:409-413`: calls to `bl sub_fc090674` and `bl sub_fc0d0472` (`PORT25-ROM-FIRMWARE-CONT`).
(c) Likely power-off/wait point: Hardware watchdog expiry if driver calls stall (Candidate 3 / Rank 3, `docs/PORT25_SHORT_PRESS_LOCALISE.md:220-231; PORT25-ROM-WATCHDOG-MODULE`), or PMIC latch timeout (Candidate 2 / Rank 4, lines 200-216) `[UNKNOWN]`.
Next candidate change: [INFERRED] Add finer LED breadcrumb between sub_fc090674 and sub_fc0d0472 (chdk-port/platform/g3x/sub/110c/boot_prototype.c:409-410; docs/PORT25_SHORT_PRESS_LOCALISE.md:409-410).

### Code 42: STAGE_BC_PRE_PHYSW_CREATE (`CODE_42`)
(a) Stage reached -> next stage: `STAGE_BC_PRE_PHYSW_CREATE` -> `STAGE_BC_POST_PHYSW_CREATE` (emitted in `tools/build_candidate_port25_ladder_fix.py:125` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:413`).
(b) Execution: `boot_prototype.c:413`: execution of `bl sub_fc1283d2` (`PORT25-ROM-PHYSW-TASK`), which spawns `task_PhySw` (`0xFC1283AD`, priority 23, stack 2048 B, `PORT25-ROM-PHYSW-TASK; PORT25-ROM-PHYSW-LITERALS`).
(c) Likely power-off/wait point: Hang in `sub_fc1283d2` task creator, watchdog timeout (Candidate 3 / Rank 3, `docs/PORT25_SHORT_PRESS_LOCALISE.md:220-231`), or PMIC latch timeout (Candidate 2 / Rank 4, lines 200-216) `[UNKNOWN]`.
Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of task_PhySw spawner sub_fc1283d2 at 0xFC1283D2 (PORT25-ROM-PHYSW-TASK; docs/PORT25_SHORT_PRESS_LOCALISE.md:169-171, 355-358).

### Code 43: STAGE_BC_POST_PHYSW_CREATE (`CODE_43`)
(a) Stage reached -> next stage: `STAGE_BC_POST_PHYSW_CREATE` -> `STAGE_BC_PRE_FIRMWARE_CONT` (emitted in `tools/build_candidate_port25_ladder_fix.py:125` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:413-418`).
(b) Execution: `boot_prototype.c:422-436`: driver initialization calls: `bl sub_fc2a75f6`, `bl sub_fc0d0488`, `bl sub_fc127f24`, `bl sub_fc0bb76e`, `bl sub_fc0d02de`, `bl sub_fc0bb9cc`, `bl sub_fc0bb72a`, `bl sub_fc05bce0`, `bl sub_fc33319a`, `bl sub_fc0bb6fe`, and continuation witness write `bl witness_record_continuation` (line 434).
(c) Likely power-off/wait point: Physical button release event detected and handled by newly running `task_PhySw` polling loop (Candidate 5 / Rank 5, `docs/PORT25_SHORT_PRESS_LOCALISE.md:250-261; PORT25-ROM-PHYSW-TASK; PORT25-ROM-PHYSW-LITERALS`), or watchdog timeout (Candidate 3 / Rank 3, lines 220-231). Shutdown edge from button release is unmapped (lines 269-272) `[UNKNOWN]`.
Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of the sub_fc1283d2 / task_PhySw power-button release path (docs/PORT25_SHORT_PRESS_LOCALISE.md:250-261, 269-272; PORT25-ROM-PHYSW-TASK).

### Code 44: STAGE_BC_PRE_FIRMWARE_CONT (`CODE_44`)
(a) Stage reached -> next stage: `STAGE_BC_PRE_FIRMWARE_CONT` -> `sub_fc0d0126` (emitted in `tools/build_candidate_port25_ladder_fix.py:126` and `chdk-port/platform/g3x/sub/110c/boot_prototype.c:437-438`; `[VERIFIED: boot_prototype.c:436-438; tools/port26_ladder_decode.py:87-91, 550]`).
(b) Execution: `boot_prototype.c:437-438`: `pop.w {r4, lr}; b.w sub_fc0d0126` restoring registers and branching into stock Canon continuation routine `sub_fc0d0126` (`PORT25-ROM-FIRMWARE-CONT`).
(c) Likely power-off/wait point: Downstream stock Canon firmware interlocks or unmapped shutdown event after handoff (Candidate 6 / Rank 6, `docs/PORT25_SHORT_PRESS_LOCALISE.md:264-275; PORT25-ROM-FIRMWARE-CONT`). TurnOffE1_FW is NOT attributed to line 438 because the control-flow edge from sub_fc0d0126 is unmapped (`PORT25_SHORT_PRESS_LOCALISE.md:269-272`) `[UNKNOWN]`.
Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of stock continuation sub_fc0d0126 reachability to TurnOffE1_FW (PORT25-ROM-FIRMWARE-CONT; docs/PORT25_SHORT_PRESS_LOCALISE.md:269-272).
