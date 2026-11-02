# PORT-26 T2b: Per-Class Next-Step Triage Plan (GM1.10C)

This plan enumerates every code and special class emitted by `tools/port26_ladder_decode.py:VALID_CLASSES` (29 ladder stage codes plus 5 special classes) and defines the stage transition, intervening execution, likely power-off point, and next candidate action `[VERIFIED: tools/port26_ladder_decode.py:161-561]`.

### Code 1: STAGE_LOADER_AFTER_PROLOGUE (`CODE_1`)
(a) Stage reached -> next stage: `STAGE_LOADER_AFTER_PROLOGUE` -> `STAGE_LOADER_AFTER_COPY` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:67, 337-340; chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:45]`. `boot_prototype.c` not yet entered.
(b) Execution: `loader_main_breadcrumb.c:54-96`: pointer setup, `core_copy(src, dst, word_len)` relocating candidate core (123,424 B, derived from `blob_chdk_core_size` at `loader_main_breadcrumb.c:57-61; docs/PORT25_LADDER_FIX_CANDIDATE.md:387-389`) to `0x003489B4`, and witness write to `0x00361170` passed via `BOOT_WITNESS_ADDR` `[VERIFIED: loader_main_breadcrumb.c:54-96; tools/build_candidate_port25_ladder_fix.py:384; docs/PORT25_LADDER_FIX_CANDIDATE.md:387-391]`.
(c) Likely power-off/wait point: Autonomous PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN: external microcontroller firmware]`, or RAM relocation stall `[UNKNOWN]`.
(d) Next candidate change: [INFERRED] Add finer LED breadcrumb immediately before core_copy() (chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:61; docs/PORT23_LED_BREADCRUMBS.md:46).

### Code 2: STAGE_LOADER_AFTER_COPY (`CODE_2`)
(a) Stage reached -> next stage: `STAGE_LOADER_AFTER_COPY` -> `STAGE_LOADER_BEFORE_DCACHE` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:67, 337-340; chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:99]`. `boot_prototype.c` not yet entered.
(b) Execution: `loader_main_breadcrumb.c:99-116`: lines 102-113 contain comments only; cache-argument loads execute after Code 3 (:119-122). Code 2 and Code 3 are adjacent breadcrumbs; interval is breadcrumb emission/timing only `[VERIFIED: loader_main_breadcrumb.c:99-116]`.
(c) Likely power-off/wait point: Autonomous PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN: external microcontroller firmware]`.
(d) Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of sub-CPU autonomous latch timeout protocol (docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216).

### Code 3: STAGE_LOADER_BEFORE_DCACHE (`CODE_3`)
(a) Stage reached -> next stage: `STAGE_LOADER_BEFORE_DCACHE` -> `STAGE_LOADER_AFTER_DCACHE` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:67, 337-340; chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:116]`. `boot_prototype.c` not yet entered.
(b) Execution: `loader_main_breadcrumb.c:118-125`: `mov r0, %0; mov r1, %1; ldr r2, =%2; blx r2` calling `ROM_DCACHE_CLEAN_INV` (`0xFC127AB1`), followed by `dsb sy` `[VERIFIED: loader_main_breadcrumb.c:118-125; PORT25-ROM-CACHE-MAINT]`.
(c) Likely power-off/wait point: Exception/hang during `ROM_DCACHE_CLEAN_INV` (`0xFC127AB1`, `PORT25-ROM-CACHE-MAINT`) or PMIC latch timeout (`docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
(d) Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of ROM_DCACHE_CLEAN_INV subroutine at 0xFC127AB1 (PORT25-ROM-CACHE-MAINT; docs/PORT25_SHORT_PRESS_LOCALISE.md:397).

### Code 4: STAGE_LOADER_AFTER_DCACHE (`CODE_4`)
(a) Stage reached -> next stage: `STAGE_LOADER_AFTER_DCACHE` -> `STAGE_LOADER_BEFORE_ICACHE` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:67, 337-340; chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:127]`. `boot_prototype.c` not yet entered.
(b) Execution: `loader_main_breadcrumb.c:127-132`: adjacent breadcrumb macros with no intervening instructions; interval is breadcrumb emission/timing only `[VERIFIED: loader_main_breadcrumb.c:127-132]`.
(c) Likely power-off/wait point: Breadcrumb emission timing delay or PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
(d) Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of PMIC power latch hold timing (docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216).

### Code 5: STAGE_LOADER_BEFORE_ICACHE (`CODE_5`)
(a) Stage reached -> next stage: `STAGE_LOADER_BEFORE_ICACHE` -> `STAGE_LOADER_AFTER_ICACHE` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:67, 337-340; chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:132]`. `boot_prototype.c` not yet entered.
(b) Execution: `loader_main_breadcrumb.c:135-143`: `mov r0, %0; mov r1, %1; ldr r2, =%3; blx r2` calling `ROM_ICACHE_INV_BP` (`0xFC127B09`), followed by `dsb sy` and `isb sy` `[VERIFIED: loader_main_breadcrumb.c:135-143; PORT25-ROM-CACHE-MAINT]`.
(c) Likely power-off/wait point: Exception/hang during `ROM_ICACHE_INV_BP` (`0xFC127B09`, `PORT25-ROM-CACHE-MAINT`) or PMIC latch timeout (`docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
(d) Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of ROM_ICACHE_INV_BP subroutine at 0xFC127B09 (PORT25-ROM-CACHE-MAINT; docs/PORT25_SHORT_PRESS_LOCALISE.md:397).

### Code 6: STAGE_LOADER_AFTER_ICACHE (`CODE_6`)
(a) Stage reached -> next stage: `STAGE_LOADER_AFTER_ICACHE` -> `STAGE_LOADER_BEFORE_BX` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:67, 337-340; chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:144]`. `boot_prototype.c` not yet entered.
(b) Execution: `loader_main_breadcrumb.c:148`: `cpsid if` enforcing disabled interrupt state prior to handoff `[VERIFIED: loader_main_breadcrumb.c:148]`.
(c) Likely power-off/wait point: Hardware fault during CPSID or PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
(d) Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of CPU mode and interrupt state at loader handoff (docs/RESTART_IRQ_PENDING_AUDIT.md:1-50; docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216).

### Code 7: STAGE_LOADER_BEFORE_BX (`CODE_7`)
(a) Stage reached -> next stage: `STAGE_LOADER_BEFORE_BX` -> `STAGE_BC_CORE_ENTRY` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:67, 110, 337-340; chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:152; chdk-port/platform/g3x/sub/110c/boot_prototype.c:91]`.
(b) Execution: loader handoff via `mov r0, %0; add r0, r0, #1; bx r0` (`chdk-port/platform/g3x/sub/110c/loader_main_breadcrumb.c:173-175`) `[VERIFIED]`; relocated core entry branches to `startup` (`chdk-port/core/entry.S:11`) `[VERIFIED]`; `startup()` performs BSS limit sanity check (`chdk-port/platform/g3x/main.c:13-16`) `[VERIFIED]`, clears CHDK BSS (`chdk-port/platform/g3x/main.c:18-19`) `[VERIFIED]`, and calls `boot()` (`chdk-port/platform/g3x/main.c:20`) `[VERIFIED]`; relocated `boot()` resets the stack pointer (`movw r0, #0x4000; movt r0, #0; mov sp, r0`, `chdk-port/platform/g3x/sub/110c/boot_prototype.c:89-91`) `[VERIFIED]`, followed immediately by Code 11 emission (`tools/build_candidate_port25_ladder_fix.py:110`) `[VERIFIED]`.
(c) Likely power-off/wait point: Branch fault during memory domain switch or PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
(d) Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of CPU execution state across bx r0 handoff to 0x003489B5 (loader_main_breadcrumb.c:173-175; boot_prototype.c:85-91; docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216).

### Code 11: STAGE_BC_CORE_ENTRY (`CODE_11`)
(a) Stage reached -> next stage: `STAGE_BC_CORE_ENTRY` -> `STAGE_BC_POST_BSS` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:110-111; chdk-port/platform/g3x/sub/110c/boot_prototype.c:91, 153-154]`.
(b) Execution: `boot_prototype.c:98-154`: `bl sub_fc02007e` (copy exception vectors, `PORT25-ROM-BOOT-EARLY`), `*(0xC0242010) |= 1`, Copy Loop 1 (High RAM), `sub_fc127a62`, Copy Loop 2 (ATCM), Copy Loop 3 (Low RAM `0x00008000..0x0003F4F4`), and Canon BSS zeroing `loc_zero_bss` (`0x0003F4F4..0x003489B4`) `[VERIFIED: boot_prototype.c:98-154]`.
(c) Likely power-off/wait point: Bus error during RAM copy loops or PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
(d) Next candidate change: [INFERRED] Add finer LED breadcrumb between sub_fc02007e vector copy and High RAM copy loop (chdk-port/platform/g3x/sub/110c/boot_prototype.c:99-106; docs/PORT25_SHORT_PRESS_LOCALISE.md:68-70).

### Code 12: STAGE_BC_POST_BSS (`CODE_12`)
(a) Stage reached -> next stage: `STAGE_BC_POST_BSS` -> `STAGE_BC_STAGE3_ENTRY` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:111-112; chdk-port/platform/g3x/sub/110c/boot_prototype.c:153-154, 174-175]`.
(b) Execution: `boot_prototype.c:159-174`: branch `b.w sub_fc05b3c8_my` (line 159), entry to `sub_fc05b3c8_my` (`push {r4, lr}` at line 171), and call `bl witness_record_core` at line 174 `[VERIFIED: boot_prototype.c:159-174]`.
(c) Likely power-off/wait point: Branch failure or witness record crash in `sub_fc05b3c8_my` (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
(d) Next candidate change: [INFERRED] Add finer LED breadcrumb immediately before witness_record_core (chdk-port/platform/g3x/sub/110c/boot_prototype.c:171-174; docs/PORT25_SHORT_PRESS_LOCALISE.md:76-77).

### Code 13: STAGE_BC_STAGE3_ENTRY (`CODE_13`)
(a) Stage reached -> next stage: `STAGE_BC_STAGE3_ENTRY` -> `STAGE_BC_PRE_KERNEL_INIT` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:112-113; chdk-port/platform/g3x/sub/110c/boot_prototype.c:174-175, 255-256]`.
(b) Execution: `boot_prototype.c:177-255`: load `new_sa` into `r4`, headroom calculation against `0x006CE000` (lines 184-188), setup Low RAM bounds at `0x00008074..0x0000807C` (lines 196-203), memset setup struct via `sub_fc31bfac`, DryOS memory descriptor setup (lines 212-250), continuation callback pointer setup `ldr r1, =sub_fc05b558_my` (line 244) `[VERIFIED: boot_prototype.c:177-255]`.
(c) Likely power-off/wait point: Headroom check verified to pass (Candidate 8, `docs/PORT25_SHORT_PRESS_LOCALISE.md:298-303; PORT25-ROM-HEAP-SETUP`) and is not the cause `[VERIFIED]`; likely cause is autonomous PMIC latch timeout (Candidate 2 / Rank 4, lines 200-216) `[UNKNOWN: external microcontroller firmware]`.
(d) Next candidate change: [INFERRED] Add finer LED breadcrumb immediately after Low RAM bounds setup (chdk-port/platform/g3x/sub/110c/boot_prototype.c:203; docs/PORT25_SHORT_PRESS_LOCALISE.md:79).

### Code 14: STAGE_BC_PRE_KERNEL_INIT (`CODE_14`)
(a) Stage reached -> next stage: `STAGE_BC_PRE_KERNEL_INIT` -> `STAGE_BC_STAGE4_ENTRY` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:113-114; chdk-port/platform/g3x/sub/110c/boot_prototype.c:255-256, 271-272]`.
(b) Execution: `boot_prototype.c:255-271`: `mov r0, sp; blx sub_fc31b408` (DryOS kernel init, `PORT25-ROM-KERNEL-INIT-VENEER`), DryOS task scheduler initialization, dispatch of Initial Task `sub_fc05b558_my` (lines 244, 268), and entry `push {r4, lr}` (line 271) `[VERIFIED: boot_prototype.c:255-271]`.
(c) Likely power-off/wait point: Hang or interrupt re-enable stall in DryOS kernel init `sub_fc31b408` (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216, 252-256; PORT25-ROM-KERNEL-INIT-VENEER`) `[UNKNOWN]`.
(d) Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of DryOS kernel initialization sub_fc31b408 and ATCM 0xBFE10F79 (PORT25-ROM-KERNEL-INIT-VENEER; docs/PORT25_SHORT_PRESS_LOCALISE.md:251-256).

### Code 15: STAGE_BC_STAGE4_ENTRY (`CODE_15`)
(a) Stage reached -> next stage: `STAGE_BC_STAGE4_ENTRY` -> `STAGE_BC_STAGE5_ENTRY` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:114-115; chdk-port/platform/g3x/sub/110c/boot_prototype.c:271-272, 344-345]`.
(b) Execution: `boot_prototype.c:272-335`: Stage 4 subsystem setup: USER_MEM check, `dmSetup` (`sub_fc418738`), `termDriverInit` (`sub_fc05c7d4`), `termDeviceCreate` (`sub_fc05c862`), `stdioSetup` (`sub_fc05b794`), `stdlibSetup` (`sub_fc05b8d8`), `extlib_setup` (`sub_fc05e910`), error checks branching to `sub_fc05b5ea` (`PORT25-ROM-INIT-TASK`), and tail branch `b.w sub_fc05b962_my` (line 334) `[VERIFIED: boot_prototype.c:272-335]`.
(c) Likely power-off/wait point: Subsystem setup error branching to `sub_fc05b5ea` (Candidate 7 / Rank 7, `docs/PORT25_SHORT_PRESS_LOCALISE.md:278-292; PORT25-ROM-INIT-TASK`), or PMIC latch timeout (Candidate 2 / Rank 4, lines 200-216) `[UNKNOWN]`.
(d) Next candidate change: [INFERRED] Add finer LED breadcrumb immediately after termDeviceCreate (chdk-port/platform/g3x/sub/110c/boot_prototype.c:306-311; docs/PORT25_SHORT_PRESS_LOCALISE.md:306-311).

### Code 21: STAGE_BC_STAGE5_ENTRY (`CODE_21`)
(a) Stage reached -> next stage: `STAGE_BC_STAGE5_ENTRY` -> `STAGE_BC_PRE_MPU_SETUP` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:115-116; chdk-port/platform/g3x/sub/110c/boot_prototype.c:344-346]`.
(b) Execution: `boot_prototype.c:344-346`: `push {r3, lr}` runs before Code 21 (`build_candidate_port25_ladder_fix.py:115`); Code 21 and Code 22 are adjacent breadcrumbs with no intervening instructions; interval is breadcrumb emission/timing only `[VERIFIED: boot_prototype.c:344-346; build_candidate_port25_ladder_fix.py:115-116]`.
(c) Likely power-off/wait point: Breadcrumb emission delay or autonomous PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
(d) Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of PMIC autonomous latch timeout timing (docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216).

### Code 22: STAGE_BC_PRE_MPU_SETUP (`CODE_22`)
(a) Stage reached -> next stage: `STAGE_BC_PRE_MPU_SETUP` -> `STAGE_BC_POST_MPU_SETUP` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:116; chdk-port/platform/g3x/sub/110c/boot_prototype.c:346]`.
(b) Execution: `boot_prototype.c:346`: call `bl sub_fc05ba68` (`PORT25-ROM-STARTUP-TASKS`), executing `pxSetup` (return-check site at `0xFC05BA6E`), `dhcpc_setup` (return-check site at `0xFC05BA82`), and MPU configuration `mpuSetup` (`0xFC135280`, `PORT25-ROM-MPU-CONFIG`) `[VERIFIED: boot_prototype.c:346; docs/PORT25_SHORT_PRESS_LOCALISE.md:284-285; PORT25-ROM-STARTUP-TASKS]`.
(c) Likely power-off/wait point: Setup failure in `pxSetup` or `dhcpc_setup` branching to `sub_fc05ba8e` (Candidate 7 / Rank 7, `docs/PORT25_SHORT_PRESS_LOCALISE.md:282-286; PORT25-ROM-STARTUP-TASKS`), or PMIC latch timeout (Candidate 2 / Rank 4, lines 200-216) `[UNKNOWN]`.
(d) Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of Stage 5 error handler sub_fc05ba8e at 0xFC05BA8E (PORT25-ROM-STARTUP-TASKS; docs/PORT25_SHORT_PRESS_LOCALISE.md:133-136, 284-286).

### Code 23: STAGE_BC_POST_MPU_SETUP (`CODE_23`)
(a) Stage reached -> next stage: `STAGE_BC_POST_MPU_SETUP` -> `STAGE_BC_PRE_POWER_CHECK` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:116-117; chdk-port/platform/g3x/sub/110c/boot_prototype.c:346-348]`.
(b) Execution: `boot_prototype.c:347`: `bl sub_fc079404` (`IsNormalCameraMode_FW` reading pointer `0xFDF20380`, `PORT25-ROM-NORMAL-MODE; PORT25-ROM-NORMAL-FLAG`) `[VERIFIED: boot_prototype.c:347]`.
(c) Likely power-off/wait point: Crash in `sub_fc079404` or PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
(d) Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of sub_fc079404 at 0xFC079404 (PORT25-ROM-NORMAL-MODE; docs/PORT25_SHORT_PRESS_LOCALISE.md:141-143).

### Code 24: STAGE_BC_PRE_POWER_CHECK (`CODE_24`)
(a) Stage reached -> next stage: `STAGE_BC_PRE_POWER_CHECK` -> `STAGE_BC_POWER_CHECK_PASS` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:117-118; chdk-port/platform/g3x/sub/110c/boot_prototype.c:347-361]`.
(b) Execution: `boot_prototype.c:348-358`: call `bl sub_fc1284ac` sampling buttons (`PORT25-ROM-POWERON-CHECK`); under `G3X_POWERON_FIX=1` (`boot_prototype.c:349`), forces `movs r0, #1; b loc_fc05b978` jumping past power cut `sub_fc05ba56` `[VERIFIED: boot_prototype.c:348-358]`.
(c) Likely power-off/wait point: In default build, button released causes `cbnz` fallthrough and GPIO 0x67 power cut in `sub_fc05ba56` (Candidate 1 / Rank 1, `docs/PORT25_SHORT_PRESS_LOCALISE.md:183-197; PORT25-ROM-STARTUP-TASKS; PORT25-ROM-GPIO-WRITE-MMIO`). In opt-in fix, `sub_fc08ecbc` is bypassed leaving startup cause at `0x00009BD0` unwritten by the opt-in `[VERIFIED: docs/PORT25_SHORT_PRESS_LOCALISE.md:238-243; PORT25-ROM-STARTCAUSE-SAVE]`, but whether this unwritten startup cause causes shutdown is `[UNKNOWN]` (initial RAM value, downstream consumers, and causal shutdown edge remain unmapped, `docs/PORT25_SHORT_PRESS_LOCALISE.md:243-246`).
(d) Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of GPIO 0x67 power latch assert mechanism and value (PORT25-ROM-GPIO-WRITE-MMIO; docs/PORT25_SHORT_PRESS_LOCALISE.md:194-215).

### Code 25: STAGE_BC_POWER_CHECK_PASS (`CODE_25`)
(a) Stage reached -> next stage: `STAGE_BC_POWER_CHECK_PASS` -> `STAGE_BC_PRE_CREATE_STARTUP` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:105, 118-119; chdk-port/platform/g3x/sub/110c/boot_prototype.c:358-373]`.
(b) Execution: `boot_prototype.c:359-369`: `blx sub_fc31b460`, `ldr r1, =0x006ce000; movs r0, #0; bl sub_fc382c8c` (ARAM heap init, `PORT25-ROM-ARAM-HEAP-INIT`), task argument setup (`movs r3, #0; str r3, [sp]; ldr r3, =task_Startup_my; movs r2, #0; movs r1, #0x19; ldr r0, =0xfc05b9a0`) `[VERIFIED: boot_prototype.c:359-369]`.
(c) Likely power-off/wait point: Allocation error or stall in ARAM heap init `sub_fc382c8c` (`PORT25-ROM-ARAM-HEAP-INIT`), or PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
(d) Next candidate change: [INFERRED] Add finer LED breadcrumb immediately after sub_fc382c8c ARAM heap init (chdk-port/platform/g3x/sub/110c/boot_prototype.c:362; docs/PORT25_SHORT_PRESS_LOCALISE.md:342, 407).

### Code 26: STAGE_BC_PRE_CREATE_STARTUP (`CODE_26`)
(a) Stage reached -> next stage: `STAGE_BC_PRE_CREATE_STARTUP` -> `STAGE_BC_STARTUP_ENTRY` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:119-120; chdk-port/platform/g3x/sub/110c/boot_prototype.c:369-384]`.
(b) Execution: `boot_prototype.c:370-384`: `blx sub_fc31bbc4` (DryOS CreateTask veneer spawning "Startup", `PORT25-ROM-CREATETASK-VENEER`), `movs r0, #0; pop {r3, pc}` exiting Initial Task, DryOS task switch, and entry to `task_Startup_my` (`push {r4, lr}` at lines 381-384) `[VERIFIED: boot_prototype.c:370-384]`.
(c) Likely power-off/wait point: Task creation failure in `sub_fc31bbc4` (`PORT25-ROM-CREATETASK-VENEER`) or scheduler dispatch delay (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
(d) Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of DryOS task creation veneer sub_fc31bbc4 and scheduler queue (PORT25-ROM-CREATETASK-VENEER; docs/PORT25_SHORT_PRESS_LOCALISE.md:366-370).

### Code 28: STAGE_BC_FAIL_POWER_CUT (`CODE_28`)
(a) Stage reached -> next stage: `STAGE_BC_FAIL_POWER_CUT` -> `STAGE_BC_HALT_SHUTDOWN` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:101; chdk-port/platform/g3x/sub/110c/boot_prototype.c:354-358]`.
(b) Execution: `boot_prototype.c:354-356`: call `bl sub_fc05ba56` (`PORT25-ROM-STARTUP-TASKS`), which writes `0x004C0003` to GPIO 0x67 (`0xD20B099C`, `PORT25-ROM-GPIO-WRITE-MMIO`) cutting system power, reaching label `loc_fc05b976` `[VERIFIED: boot_prototype.c:354-356]`.
(c) Likely power-off/wait point: Native button check failure de-asserting GPIO 0x67 power latch in `sub_fc05ba56` (Candidate 1 / Rank 1, `docs/PORT25_SHORT_PRESS_LOCALISE.md:183-197; PORT25-ROM-STARTUP-TASKS; PORT25-ROM-GPIO-WRITE-MMIO`) `[VERIFIED: boot_prototype.c:354-356; docs/PORT25_SHORT_PRESS_LOCALISE.md:183-197]`.
(d) Next candidate change: [VERIFIED] Enable G3X_POWERON_FIX=1 to bypass sub_fc05ba56 power-cut branch (chdk-port/platform/g3x/sub/110c/boot_prototype.c:348-355; docs/PORT24_POWERON_FIX.md:19-24; docs/PORT25_SHORT_PRESS_LOCALISE.md:152-155).

### Code 29: STAGE_BC_HALT_SHUTDOWN (`CODE_29`)
(a) Stage reached -> next stage: `STAGE_BC_HALT_SHUTDOWN` -> None `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:102-103; chdk-port/platform/g3x/sub/110c/boot_prototype.c:356-358; tools/port26_ladder_decode.py:541]`.
(b) Execution: In the generated candidate, `CORE_LADDER_PULSE_29` sits after `loc_fc05b976` and branches back to that label (`tools/build_candidate_port25_ladder_fix.py:102-103; boot_prototype.c:356-358`). The interval is this breadcrumb emission/timing loop repeating for as long as hardware power holds `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:102-103]`; the observable consequence is a repeating Code 29 pulse sequence until power collapse `[INFERRED: tools/build_candidate_port25_ladder_fix.py:102-103; docs/PORT25_SHORT_PRESS_LOCALISE.md:194-197]`.
(c) Likely power-off/wait point: Breadcrumb emission/timing loop following GPIO 0x67 power cut (Candidate 1 / Rank 1, `docs/PORT25_SHORT_PRESS_LOCALISE.md:194-197, 368; PORT25-ROM-STARTUP-TASKS`) `[VERIFIED: boot_prototype.c:356-358; tools/build_candidate_port25_ladder_fix.py:102-103; docs/PORT25_SHORT_PRESS_LOCALISE.md:194-197, 368]`.
(d) Next candidate change: [VERIFIED] Enable G3X_POWERON_FIX=1 to branch directly to loc_fc05b978 and bypass halt loop (chdk-port/platform/g3x/sub/110c/boot_prototype.c:348-355; docs/PORT24_POWERON_FIX.md:19-24; docs/PORT25_SHORT_PRESS_LOCALISE.md:152-155).

### Code 31: STAGE_BC_STARTUP_ENTRY (`CODE_31`)
(a) Stage reached -> next stage: `STAGE_BC_STARTUP_ENTRY` -> `STAGE_BC_POST_EARLY_INIT` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:120-121; chdk-port/platform/g3x/sub/110c/boot_prototype.c:381-393]`.
(b) Execution: `boot_prototype.c:384-388`: calls to early Canon driver subroutines: `bl sub_fc0d0150` (spawns "ClockSave", `PORT25-ROM-FIRMWARE-CONT`), `bl sub_fc05ba34`, `bl sub_fc05bb94`, and `bl sub_fc418eec` (`PORT25-ROM-STARTUP-TASKS`) `[VERIFIED: boot_prototype.c:384-388]`.
(c) Likely power-off/wait point: Crash or hang inside early driver routines `sub_fc0d0150..sub_fc418eec` (`PORT25-ROM-FIRMWARE-CONT; PORT25-ROM-STARTUP-TASKS`), or PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
(d) Next candidate change: [INFERRED] Add finer LED breadcrumb immediately after sub_fc0d0150 ClockSave task creation (chdk-port/platform/g3x/sub/110c/boot_prototype.c:385; docs/PORT25_SHORT_PRESS_LOCALISE.md:164-166).

### Code 32: STAGE_BC_POST_EARLY_INIT (`CODE_32`)
(a) Stage reached -> next stage: `STAGE_BC_POST_EARLY_INIT` -> `STAGE_BC_PRE_SD1STINIT` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:121-122; chdk-port/platform/g3x/sub/110c/boot_prototype.c:388-402]`.
(b) Execution: `tools/build_candidate_port25_ladder_fix.py:121-122`, `chdk-port/platform/g3x/sub/110c/boot_prototype.c:389-397`: lines 390-396 contain comments only; Code 32 and Code 33 are adjacent breadcrumbs with no intervening calls or initializers. Interval is breadcrumb emission/timing only `[VERIFIED: boot_prototype.c:389-397; build_candidate_port25_ladder_fix.py:121-122]`.
(c) Likely power-off/wait point: Breadcrumb emission timing delay or autonomous PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
(d) Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of PMIC autonomous latch timeout duration (docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216).

### Code 33: STAGE_BC_PRE_SD1STINIT (`CODE_33`)
(a) Stage reached -> next stage: `STAGE_BC_PRE_SD1STINIT` -> `STAGE_BC_POST_SD1STINIT` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:122-123; chdk-port/platform/g3x/sub/110c/boot_prototype.c:397-407]`.
(b) Execution: `boot_prototype.c:397-402`: `movs r0, #0; bl sub_fc05c4e0` querying card switch gate (`PORT25-ROM-CARD-SWITCHES`), `lsls r0, r0, #31; bne 1f`, and conditional task creation `blx sub_fc31b1f4` spawning "SD1stInit" (`PORT25-ROM-SD1STINIT-VENEER`) `[VERIFIED: boot_prototype.c:397-402]`.
(c) Likely power-off/wait point: SD card switch query fault in `sub_fc05c4e0` (`PORT25-ROM-CARD-SWITCHES`) or task spawn failure in `sub_fc31b1f4` (`PORT25-ROM-SD1STINIT-VENEER`), or PMIC latch timeout (`docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
(d) Next candidate change: [INFERRED] Add finer LED breadcrumb immediately after sub_fc05c4e0 switch check (chdk-port/platform/g3x/sub/110c/boot_prototype.c:398; docs/PORT25_SHORT_PRESS_LOCALISE.md:390, 403).

### Code 34: STAGE_BC_POST_SD1STINIT (`CODE_34`)
(a) Stage reached -> next stage: `STAGE_BC_POST_SD1STINIT` -> `STAGE_BC_PRE_WATCHDOG_START` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:123-124; chdk-port/platform/g3x/sub/110c/boot_prototype.c:402-408]`.
(b) Execution: `boot_prototype.c:403-408`: sequential calls to driver routines: `bl sub_fc0bba02`, `bl sub_fc0d046c`, `bl sub_fc05bcdc`, and `bl sub_fc05bb24` (`PORT25-ROM-STARTDISKBOOT; PORT25-ROM-FIRMWARE-CONT`) `[VERIFIED: boot_prototype.c:403-408]`.
(c) Likely power-off/wait point: Crash or hang in driver setup calls `sub_fc0bba02..sub_fc05bb24`, or PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
(d) Next candidate change: [INFERRED] Add finer LED breadcrumb immediately after sub_fc0d046c (chdk-port/platform/g3x/sub/110c/boot_prototype.c:405; docs/PORT25_SHORT_PRESS_LOCALISE.md:405).

### Code 35: STAGE_BC_PRE_WATCHDOG_START (`CODE_35`)
(a) Stage reached -> next stage: `STAGE_BC_PRE_WATCHDOG_START` -> `STAGE_BC_POST_WATCHDOG_START` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:124; chdk-port/platform/g3x/sub/110c/boot_prototype.c:408-413]`.
(b) Execution: `boot_prototype.c:408`: execution of `bl sub_fc418f2a` (`PORT25-ROM-WATCHDOG-START`), which configures and starts the hardware watchdog timer via `StartWDT_FW` (`0xFC135D2C`, `PORT25-ROM-WATCHDOG-MODULE`) `[VERIFIED: boot_prototype.c:408]`.
(c) Likely power-off/wait point: Hang inside watchdog start routine `sub_fc418f2a` (`PORT25-ROM-WATCHDOG-START; PORT25-ROM-WATCHDOG-MODULE`), or PMIC latch timeout (Candidate 2 / Rank 4, `docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216`) `[UNKNOWN]`.
(d) Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of StartWDT_FW MMIO registers at 0xFC135D2C and 0xD20A0000 (PORT25-ROM-WATCHDOG-MODULE; docs/PORT25_SHORT_PRESS_LOCALISE.md:221-226).

### Code 41: STAGE_BC_POST_WATCHDOG_START (`CODE_41`)
(a) Stage reached -> next stage: `STAGE_BC_POST_WATCHDOG_START` -> `STAGE_BC_PRE_PHYSW_CREATE` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:124-125; chdk-port/platform/g3x/sub/110c/boot_prototype.c:408-413]`.
(b) Execution: `boot_prototype.c:409-413`: calls to `bl sub_fc090674` and `bl sub_fc0d0472` (`PORT25-ROM-FIRMWARE-CONT`) `[VERIFIED: boot_prototype.c:409-413]`.
(c) Likely power-off/wait point: Hardware watchdog expiry if driver calls stall (Candidate 3 / Rank 3, `docs/PORT25_SHORT_PRESS_LOCALISE.md:220-231; PORT25-ROM-WATCHDOG-MODULE`), or PMIC latch timeout (Candidate 2 / Rank 4, lines 200-216) `[UNKNOWN]`.
(d) Next candidate change: [INFERRED] Add finer LED breadcrumb between sub_fc090674 and sub_fc0d0472 (chdk-port/platform/g3x/sub/110c/boot_prototype.c:409-410; docs/PORT25_SHORT_PRESS_LOCALISE.md:409-410).

### Code 42: STAGE_BC_PRE_PHYSW_CREATE (`CODE_42`)
(a) Stage reached -> next stage: `STAGE_BC_PRE_PHYSW_CREATE` -> `STAGE_BC_POST_PHYSW_CREATE` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:125; chdk-port/platform/g3x/sub/110c/boot_prototype.c:413]`.
(b) Execution: `boot_prototype.c:413`: execution of `bl sub_fc1283d2` (`PORT25-ROM-PHYSW-TASK`), which inspects existing task state and conditionally creates `task_PhySw` (`0xFC1283AD`, priority 23, stack 2048 B, `PORT25-ROM-PHYSW-TASK; PORT25-ROM-PHYSW-LITERALS; docs/PORT25_SHORT_PRESS_LOCALISE.md:355-358`) `[STATIC_VERIFIED: PORT25-ROM-PHYSW-TASK; docs/PORT25_SHORT_PRESS_LOCALISE.md:355-358]`.
(c) Likely power-off/wait point: Hang in `sub_fc1283d2` task creator, watchdog timeout (Candidate 3 / Rank 3, `docs/PORT25_SHORT_PRESS_LOCALISE.md:220-231`), or PMIC latch timeout (Candidate 2 / Rank 4, lines 200-216) `[UNKNOWN]`.
(d) Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of task_PhySw spawner sub_fc1283d2 at 0xFC1283D2 (PORT25-ROM-PHYSW-TASK; docs/PORT25_SHORT_PRESS_LOCALISE.md:169-171, 355-358).

### Code 43: STAGE_BC_POST_PHYSW_CREATE (`CODE_43`)
(a) Stage reached -> next stage: `STAGE_BC_POST_PHYSW_CREATE` -> `STAGE_BC_PRE_FIRMWARE_CONT` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:125-126; chdk-port/platform/g3x/sub/110c/boot_prototype.c:413-438]`. VERIFIED: the `sub_fc1283d2` helper returned, because Code 43 is emitted after it `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:125; chdk-port/platform/g3x/sub/110c/boot_prototype.c:413]`.
(b) Execution: `boot_prototype.c:422-436`: driver initialization calls: `bl sub_fc2a75f6`, `bl sub_fc0d0488`, `bl sub_fc127f24`, `bl sub_fc0bb76e`, `bl sub_fc0d02de`, `bl sub_fc0bb9cc`, `bl sub_fc0bb72a`, `bl sub_fc05bce0`, `bl sub_fc33319a`, `bl sub_fc0bb6fe`, and continuation witness write `bl witness_record_continuation` (line 434) `[VERIFIED: boot_prototype.c:422-436]`. UNKNOWN: whether `task_PhySw` was created `[UNKNOWN: docs/PORT25_SHORT_PRESS_LOCALISE.md:355-358]`.
(c) Likely power-off/wait point: UNKNOWN: whether `task_PhySw` ran or sent any event `[UNKNOWN: docs/PORT25_SHORT_PRESS_LOCALISE.md:355-358]`. Any link to the power-button release can be at most INFERRED, citing the owner's 2026-11-02 report (Candidate 5 / Rank 5, `docs/PORT25_SHORT_PRESS_LOCALISE.md:250-261`) `[INFERRED: owner observation, 2026-11-02]`. Driver initialization stall or watchdog timeout (Candidate 3 / Rank 3, lines 220-231) are also possible `[UNKNOWN]`. The shutdown edge from button release remains unmapped (`docs/PORT25_SHORT_PRESS_LOCALISE.md:269-272`) `[UNKNOWN]`. (See `docs/PORT26_TRIAL_2026-11-02.md` for the full optical decode and triage analysis of the 2026-11-02 owner trial).
(d) Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of the sub_fc1283d2 / task_PhySw power-button release path (PORT25_SHORT_PRESS_LOCALISE.md:269-272).

### Code 44: STAGE_BC_PRE_FIRMWARE_CONT (`CODE_44`)
(a) Stage reached -> next stage: `STAGE_BC_PRE_FIRMWARE_CONT` -> `sub_fc0d0126` `[VERIFIED: tools/build_candidate_port25_ladder_fix.py:126; chdk-port/platform/g3x/sub/110c/boot_prototype.c:437-438; tools/port26_ladder_decode.py:550]`.
(b) Execution: `boot_prototype.c:437-438`: `pop.w {r4, lr}; b.w sub_fc0d0126` restoring registers and branching into stock Canon continuation routine `sub_fc0d0126` (`PORT25-ROM-FIRMWARE-CONT`) `[VERIFIED: boot_prototype.c:437-438]`.
(c) Likely power-off/wait point: Downstream stock Canon firmware interlocks or unmapped shutdown event after handoff (Candidate 6 / Rank 6, `docs/PORT25_SHORT_PRESS_LOCALISE.md:264-275; PORT25-ROM-FIRMWARE-CONT`). TurnOffE1_FW is NOT attributed to line 438 because the control-flow edge from sub_fc0d0126 is unmapped (`PORT25_SHORT_PRESS_LOCALISE.md:269-272`) `[UNKNOWN]`.
(d) Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of stock continuation sub_fc0d0126 reachability to TurnOffE1_FW (PORT25-ROM-FIRMWARE-CONT; docs/PORT25_SHORT_PRESS_LOCALISE.md:269-272).

### NO_PULSES (`NO_PULSES`)
(a) Stage reached -> next stage: `UNKNOWN (no LED evidence)` -> `UNKNOWN (no LED evidence)`. No checkpoint was observed optically; only the literal `'none'` maps to `NO_PULSES` (numeric `0` maps to `UNKNOWN_CODE`), and boot progress is UNKNOWN `[VERIFIED: tools/port26_ladder_decode.py:1840-1865, 1869-1885; docs/PORT25_OWNER_TRIAL_PLAN.md:201; docs/PORT25_LADDER_FIX_CANDIDATE.md:328]`.
(b) Execution: No checkpoint was observed optically and boot progress is UNKNOWN; no LED evidence recorded in trial table `[UNKNOWN: tools/port26_ladder_decode.py:1840-1865]`.
(c) Likely power-off/wait point: Power-off or wait point is UNKNOWN due to absence of optical observations (Candidate 2 / Rank 4 autonomous PMIC timeout, or pre-loader failure) `[UNKNOWN: tools/port26_ladder_decode.py:1840-1865; docs/PORT25_OWNER_TRIAL_PLAN.md:201; docs/PORT25_SHORT_PRESS_LOCALISE.md:200-216]`.
(d) Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of pre-loader boot stages or video re-capture with verified camera alignment (tools/port26_ladder_decode.py:1840-1865; docs/PORT25_OWNER_TRIAL_PLAN.md:201; docs/PORT25_LADDER_FIX_CANDIDATE.md:328).

### UNKNOWN_CODE (`UNKNOWN_CODE`)
(a) Stage reached -> next stage: Unregistered code; stage information is unavailable because the reported pulse count does not match any valid ladder code in `LADDER_STAGE_TABLE` (valid: 1..7, 11..15, 21..26, 28..29, 31..35, 41..44) or is a numeric non-positive integer (`<= 0`) `[VERIFIED: tools/port26_ladder_decode.py:557, 1869-1885; docs/PORT25_LADDER_FIX_CANDIDATE.md:326-354]`.
(b) Execution: Pulse observation does not correlate with any registered ladder checkpoint in candidate loader or core `[UNKNOWN: tools/port26_ladder_decode.py:1869-1885]`.
(c) Likely power-off/wait point: Optical count error, spurious hardware LED activity, or unmapped firmware interrupt handler `[UNKNOWN: tools/port26_ladder_decode.py:1869-1885]`. Remedy: correct the owner report or re-capture video to resolve a registered pulse count `[VERIFIED: tools/port26_ladder_decode.py:1869-1885; docs/PORT25_LADDER_FIX_CANDIDATE.md:326-354]`.
(d) Follow-up UNKNOWN: needs control-flow mapping of the unresolved stage interval, which cannot be chosen until owner report correction or video re-capture resolves a registered pulse count (tools/port26_ladder_decode.py:1869-1885; docs/PORT25_LADDER_FIX_CANDIDATE.md:326-354).

### AMBIGUOUS (`AMBIGUOUS`)
(a) Stage reached -> next stage: Indeterminate stage; decoder returns `AMBIGUOUS` in three distinct cases: (1) conflicting duplicate keys, raised before candidate verification (`tools/port26_ladder_decode.py:1680-1694`), where candidate identity is not established `[VERIFIED: tools/port26_ladder_decode.py:1680-1694]`; (2) distinct pulse counts reported in one report, raised after candidate verification (`tools/port26_ladder_decode.py:1824-1838`), where candidate identity is established but stage is not `[VERIFIED: tools/port26_ladder_decode.py:1824-1838]`; and (3) flagged off-by-one uncertainty adjacent to two valid codes, raised after candidate verification (`tools/port26_ladder_decode.py:1887-1906`), where candidate identity is established but stage is not `[VERIFIED: tools/port26_ladder_decode.py:1887-1906]`.
(b) Execution: Execution progress is UNKNOWN because conflicting keys or ambiguous pulse counts prevent mapping execution to a specific candidate stage interval `[UNKNOWN: tools/port26_ladder_decode.py:1680-1694, 1824-1838, 1887-1906]`.
(c) Likely power-off/wait point: Power-off or wait point is UNKNOWN `[UNKNOWN]`. Remedy: re-submitting without conflicting keys fixes only case (a) `[VERIFIED: tools/port26_ladder_decode.py:1680-1694]`; cases (b) and (c) require clearer pulse evidence by re-decoding recording frame by frame against gap thresholds (`docs/PORT25_OWNER_TRIAL_PLAN.md:155-161`) or adding a clarifying note from owner `[VERIFIED: tools/port26_ladder_decode.py:1824-1838, 1887-1906; docs/PORT25_OWNER_TRIAL_PLAN.md:155-161]`.
(d) Follow-up UNKNOWN: needs control-flow mapping of the unresolved stage interval, which cannot be chosen until report re-submission without conflicting keys or clearer pulse evidence (tools/port26_ladder_decode.py:1680-1694, 1824-1838, 1887-1906; docs/PORT25_OWNER_TRIAL_PLAN.md:155-161).

### INVALID_CANDIDATE (`INVALID_CANDIDATE`)
(a) Stage reached -> next stage: No stage claim at all; stage information is unavailable because reported DISKBOOT SHA-256 does not match expected combined-candidate digest (`9ba62067...3a15`) `[VERIFIED: tools/port26_ladder_decode.py:559, 1696-1708; docs/PORT25_LADDER_FIX_CANDIDATE.md:385; docs/PORT25_OWNER_TRIAL_PLAN.md:30, 81]`.
(b) Execution: An untrusted or non-candidate binary executed instead of the verified combined-candidate artifact `[UNKNOWN: tools/port26_ladder_decode.py:1696-1708]`.
(c) Likely power-off/wait point: Non-candidate binary execution failure, uninstrumented build, or wrong file deployed to SD card `[UNKNOWN: tools/port26_ladder_decode.py:1696-1708]`. Remedy: correct owner report or re-run trial with verified combined candidate DISKBOOT artifact `[VERIFIED: tools/port26_ladder_decode.py:1696-1708; docs/PORT25_LADDER_FIX_CANDIDATE.md:385; docs/PORT25_OWNER_TRIAL_PLAN.md:30, 81]`.
(d) Follow-up UNKNOWN: needs control-flow mapping of the unresolved stage interval, which cannot be chosen until report correction or re-run with verified candidate DISKBOOT artifact (tools/port26_ladder_decode.py:1696-1708; docs/PORT25_LADDER_FIX_CANDIDATE.md:385).

### CONTROL_HELD_O1 (`CONTROL_HELD_O1`)
(a) Stage reached -> next stage: Stock UI reached; ladder breadcrumb stage transition is not applicable because power was maintained externally via held power button `[VERIFIED: tools/port26_ladder_decode.py:560, 1710-1728; docs/PORT24_POWERON_FIX.md:19-24; docs/PORT25_SHORT_PRESS_LOCALISE.md:21, 55]`.
(b) Execution: Stock Canon firmware boot completed successfully to live shooting/playback GUI under held button press (Outcome O1/O6) `[VERIFIED: tools/port26_ladder_decode.py:1710-1728; docs/PORT24_POWERON_FIX.md:19-24; docs/PORT25_OWNER_TRIAL_PLAN.md:162-173]`.
(c) Likely power-off/wait point: Camera does not power off; boots fully to stock UI, verifying baseline hardware health and positive control `[VERIFIED: tools/port26_ladder_decode.py:1710-1728; docs/PORT25_OWNER_TRIAL_PLAN.md:162-173]`.
(d) Follow-up UNKNOWN: needs bounded ROM range / control-flow mapping of short-press release path differences from held-press baseline (docs/PORT25_SHORT_PRESS_LOCALISE.md:21, 55, 250-261).
