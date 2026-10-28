# PORT-4F — Verified native capability inventory

Review/local retrieval date: **2026-10-25 (Asia/Seoul)**. Reviewer: Codex, independent evidence reviewer.
Workspace: `/Users/avp/Project/g3x-lite`; branch `docs/port3-restart-readiness-audit`; review-start HEAD `4577fb6ae74057571da923b51f61fbe0724a1595`. Existing modified/untracked work is preserved.

**Final verdict: `INFORMATIONAL_ONLY`.** The five owner-reported GM1.10C packages demonstrate **four distinct Canon routines called by custom native payloads**: `LCDMsg_SetStr_native`, `LCDMsg_ChangeColor_native`, `GetKbdState` and `SleepTask`. They support copied text/color output, passive keyboard observation and bounded yield/resume. None demonstrates native AF lock, focus-mode selection, exposure control, recording control or an actionable settings menu.

Here “actionable” means changing a selected camera function or dispatching a working UI command. Message text/color changes are real UI effects, but do not establish such control. The verdict does not deny the demonstrated input-reading or scheduling primitive; it identifies the extent of demonstrated product functionality.

## 1. Scope and confidence rules

Question: **Which capabilities are actually supported for short native execution borrowed from `task_Script`, and what is merely identified?** Only existing project documentation was read. No ROM, binary, loader, source implementation or test implementation was opened for analysis. No disassembly, classifier-blocked investigation, camera/SD operation, executable edit, build, test execution, deployment, commit or push occurred. Markdown/file-identity checks are documentation bookkeeping. Outputs are this report and required brief PROJECT_STATE/HANDOFF additions.

Three classifications apply to a stated proposition, not to an API name in isolation:

- **VERIFIED:** documented owner observation, or documented static fact, with that evidence type stated. Hardware observations are attributed to their reports; they were not independently reproduced here.
- **PLAUSIBLE:** evidence supports a potential use, but its contract or user-visible result is unproved.
- **UNKNOWN:** the required evidence is missing. Static identification alone does not establish safe callability from custom native code, and no missing mechanism is supplied here.

Four contexts must remain separate:

1. **Payload call:** the custom native payload directly calls a Canon routine while inside the synchronous `exec` call. These are the four routines in §3.
2. **Loader event procedure:** Canon Basic calls a registered interface before/after the payload. Successful loader use does not establish the corresponding raw native entry's ABI or context contract.
3. **Direct maintenance dispatch:** the loader separately uses `exec` for cache maintenance before payload entry. This is native dispatch from the script context, but is infrastructure, not a payload feature API.
4. **Canon internal work:** Canon's tasks render text or process their own input after custom code returns. Transitive firmware calls do not become separately demonstrated custom-call APIs.

The inventory covers named external calls documented for the five packages, not every internal function reached inside Canon firmware. Runtime error branches are not marked demonstrated merely because a reviewed loader contains them. No applicability to another firmware revision is inferred.

## 2. Five-package evidence map

H1–H5 denote the hardware reports below; R1–R5 denote their associated artifact reviews. Artifact sizes and call counts are those recorded in the documents, not newly measured from executables.

| Package / observation date | Direct Canon routines in the native payload | Strongest recorded result | Limits |
|---|---|---|---|
| **H1: BOOT-001A**, 2026-10-17; [hardware §§1–5](BOOT001A_HARDWARE_RESULT.md), [R1 final delta review](BOOT001A_FINAL_DELTA_REVIEW.md) | **None.** The 12-byte leaf returns a sentinel. | Loader displayed the expected returned sentinel; subsequent normal operation reported. **VERIFIED, owner report + reviewed path.** | LCD output belongs to the loader, not the leaf. Does not demonstrate any feature API. |
| **H2: BOOT-001B-DIAG**, 2026-10-17; [hardware §§1–4](BOOT001B_DIAG_HARDWARE_RESULT.md), [R2 final review](BOOT001B_DIAG_FINAL_REVIEW.md) | `LCDMsg_SetStr_native` once in the 52-byte payload. | Both `RET_OK` and native-only text appeared after Playback→Shooting. **VERIFIED, owner report + reviewed path.** | Pre-existing handle supplied by loader; Basic did not overwrite that native text after dispatch. No external photo/video recorded. |
| **H3: UI-001A**, 2026-10-18; [hardware §§1–4](UI001A_HARDWARE_RESULT.md), [R3 final review](UI001A_FINAL_REVIEW.md) | `LCDMsg_ChangeColor_native` three times; `LCDMsg_SetStr_native` three times in the 156-byte payload. | All three specified lines/colors appeared after return and transition. **VERIFIED, owner report + reviewed call sequence.** | “System Info” and “Settings” were labels. No input handling. R3 notes no independently visible numeric return sentinel. No external photo/video recorded. |
| **H4: UI-001B-0**, 2026-10-18; [hardware §§1, 3–4](UI001B0_HARDWARE_RESULT.md), [R4 alignment-remediation review §§2, 7](UI001B0_GEMINI_INDEPENDENT_REVIEW.md) | `GetKbdState` once; `LCDMsg_ChangeColor_native` three times; `LCDMsg_SetStr_native` three times in the 420-byte payload. | Three keyboard words displayed with `CAN: OK`; report cites an owner photograph. **VERIFIED, documented observation.** | One snapshot, not dynamic key mapping or event handling. Canaries concern the tested result-buffer boundaries, not all memory. |
| **H5: UI-001B-1**, 2026-10-18; [hardware §§1, 3–5](UI001B1_HARDWARE_RESULT.md), [R5 final review §§2–5](UI001B1_FINAL_REVIEW.md) | `SleepTask`, `GetKbdState`, `LCDMsg_ChangeColor_native`, `LCDMsg_SetStr_native` in the 676-byte payload. | Bounded sampling/yield/resume, final differences and intact canaries reported. **VERIFIED, owner report + reviewed path.** | Ten settling and fifty sampling sleeps; one baseline plus fifty sample reads in the documented normal path. About 1.8 s is nominal, not a measured upper bound. No continuing custom task. |

These are five package families, not five independent replications of every API. The earlier original BOOT-001B attempt was **inconclusive**; it is not a sixth successful test or evidence for its removed wait/delete behavior. [R2, introduction](BOOT001B_DIAG_FINAL_REVIEW.md).

## 3. Demonstrated direct native API capability table

| Canon routine | Demonstrated custom-native use | Capability classification | What it does not prove |
|---|---|---|---|
| `LCDMsg_SetStr_native` (also shortened to `SetStr_native` in reviews) | H2–H5: update loader-created valid handles; documents record string copying into Canon message storage before return. | **VERIFIED** for the tested handles, strings and script context. Informational text output can outlive the payload because Canon holds a copy. | Native creation/deletion, live rendering during Playback execution, arbitrary dialogs, command dispatch, unlimited text, indefinite display lifetime or another API's argument copying. |
| `LCDMsg_ChangeColor_native` (`ChangeColor_native`) | H3–H5: set descriptor colors; H3 visibly distinguishes green/white lines. | **VERIFIED** for tested message colors/handles. | Palette suppression, global OSD control, visibility in every mode, or a working setting behind the colored label. |
| `GetKbdState` | H4: fill a caller-owned three-word snapshot; H5: repeat reads during a bounded window. | **VERIFIED** for these reads/buffers/context. Passive input observation. | Posting, consuming or suppressing a key event; triggering a function; complete button mapping; focus state, exposure state or recording state readout. |
| `SleepTask` | H5: yield and resume within the existing borrowed Canon task during a bounded call. | **VERIFIED** for this package's sleep/yield/resume path. | Creating a task, code remaining executable after return, releasing the interpreter's mode-transition dependency, a general time budget, or real-time scheduling guarantees. |

**Native return and local formatting:** sentinel generation, hexadecimal conversion, XOR accumulation and canary checks also ran in the reviewed payloads. They are custom computations, **not additional Canon APIs**. In particular, `hex32_internal` is a local helper, not proof of native `sprintf` callability. Canon-internal copying, redraw posting or scheduling beneath the four routines is likewise not separately demonstrated direct use.

PORT-4C's “at least one API” gate is a conservative minimum, not an exhaustive API count. H3/R3 establish color calls, H4/R4 establish input reads and H5/R5 establish sleep calls in addition to H2's text setter. [PORT-4C §§2, 8](PORT4C_MEMORY_OWNERSHIP_LIFETIME.md).

### 3.1 Loader and maintenance capabilities, separately attributed

The following named interfaces occur in documented loader paths. **VERIFIED loader use** means a reviewed path associated with an owner-success report; there is no independent per-call trace. It does not mean every error outcome, raw native variant or arbitrary future use is verified.

| API / operation | Documented use in the packages | Classification and boundary |
|---|---|---|
| `ExecuteEventProcedure` dispatch of `exec` | All five: synchronous payload entry and return; separate pre-payload maintenance calls. H1/R1, H2/R2, PORT-4C §§2–4. | **VERIFIED** bridge behavior for the tested packages. Does not establish arbitrary target/API safety. |
| D-cache clean and I-cache invalidate routines (documented as DCCSW and ICIALLU maintenance) | Loader dispatches the two recorded routines through `exec` before payload entry. H1/H2, R5 §5, PORT-4C G2. | **VERIFIED** documented dispatch/use as part of successful packages; not isolated measurements of every cache effect, full cache topology or long-term coherence. These are not two extra payload feature APIs. |
| `System.Create`, `UI.CreatePublic` | Registration/setup preceding the tested payload paths; named in R2/R3/R4/R5 and the [BOOT-001A design's loader section](BOOT001_MINIMAL_POC_DESIGN.md). | **VERIFIED** documented loader setup use. No arbitrary UI-control capability follows from successful registration. |
| `LCDMsg_Create`, `LCDMsg_Move` | Loader creates and positions the handles later supplied to native code; H2/H3 and R2/R3 describe the actual paths. | **VERIFIED** documented Basic-interface use. Direct custom-native constructor/move calls remain **UNKNOWN** in these tests. |
| `LCDMsg_SetStr`, `LCDMsg_ChangeColor` (Basic interfaces) | Loader initializes status/output objects; H1's PASS display is a loader setter, and R2 separates Basic/native output. | **VERIFIED** documented loader UI use. Keep separate from §3's direct native demonstrations. |
| `AllocateMemory`, `FreeMemory` | Loader obtains payload/scratch buffers and explicitly frees them after return. PORT-4C E1–E5; R1–R5. | **VERIFIED** documented loader lifecycle. No payload-level allocation/free demonstration or un-freed block survival after script exit is established. |
| `Fopen_Fut`, `Fread_Fut`, `Fclose_Fut` | Loader reads the package into its buffer before native dispatch. R1 close/read review; R2–R5 loading reviews. | **VERIFIED** documented successful loader path. Native file I/O, recording-time storage access, write/flush behavior and injected-failure paths are **UNKNOWN** from these five tests. |
| `memcmp`, `strcmp` | Loader compatibility comparisons; `memcmp` also checks input-probe canaries after return. BOOT-001A design, R4 §7, R5 §§4–5. | **VERIFIED** documented loader comparison use. Not independent demonstrations of calls from the custom payload. |
| `Wait` | BOOT-001A design documents loader waits, including a post-payload wait; R1 explicitly mentions the intended three-second wait. H2's successful diagnostic removes the prior BOOT-B wait. | **VERIFIED** documented inclusion in BOOT-001A's reviewed loader; isolated runtime timing/semantics **UNKNOWN**. Not a leaf-payload API and not the H5 native `SleepTask` demonstration. |
| `LCDMsg_Delete` / `LCDMsg_Delete_native` | Scoped rollback appears in reviewed UI loader error branches; the successful UI paths retain descriptors. R3 rollback section, R4 §7. R2 has no executable delete. | **VERIFIED** static identification/branch presence; execution in these successful sessions and direct custom-native deletion **UNKNOWN**. No tested repeat/dismissal lifecycle follows. |

Functions used internally by the allocator (`malloc`, `free`, semaphore services and heap helpers) are documented static internals in [PORT-4D §2](PORT4D_G6_ALLOCATION_OWNERSHIP_AUDIT.md). They are not further independently demonstrated APIs callable directly by custom payloads. Similarly, these tests do not establish direct payload use of `Fwrite_Fut`, `sprintf`, general `memcpy` or `strlen` merely because related services appear in other documents or inside a called routine.

## 4. Identified but untested feature-control candidates

The runtime question in this table is **callable with the intended effect from short custom native execution inside `task_Script`**. It remains UNKNOWN for every row. VERIFIED static identity and PLAUSIBLE feature potential must not be substituted for that runtime contract. No entry address, prototype, invocation sequence or patch design is selected here.

| API / capability | Existing evidence | Static/potential classification | Runtime control classification |
|---|---|---|---|
| `SS.DoAFLock`, `SS.UnlockAF` | [GM1.10C function map §1](GM110C_FUNCTION_MAP.md): confirmed named wrapper bindings; targets are candidates. [RESEARCH_LOG E008](RESEARCH_LOG.md): stock AF lock exists, unavailable in Servo AF. | Identity **VERIFIED** as a documented static finding; a stock-AF shortcut is **PLAUSIBLE**. | **UNKNOWN**: none of H1–H5 calls them. |
| `SS.MFOn`, `SS.MFOff` | Same map §1; G5 X MF wrappers are comparable-camera source evidence in [RESEARCH_LOG E023](RESEARCH_LOG.md). | Named bindings **VERIFIED** statically; one-shot mode access **PLAUSIBLE** in principle. G5 X behavior is not a G3 X task-context result. | **UNKNOWN**: no focus-mode transition demonstrated. |
| `MoveFocusLensWithDistance`, `MoveFocusLensToDistance`, `GetFocusLensSubjectDistance` | Function map §2 records bindings; units, prototypes and layer remain unresolved. G5 X focus movement has an MF-state crash caveat. | Bindings **VERIFIED** statically; safe G3 X lens-control/readout contract absent. | **UNKNOWN**, including safe readout, completion, motion limits and error handling. |
| `MovieAF.Suspend`, `MovieAF.Resume` | Function map §4: named bindings, unreviewed semantics. | Binding identity **VERIFIED** statically. | **UNKNOWN**; no movie-AF effect demonstrated. |
| `SS.DoAELock`, `SS.UnlockAE` | Function map §1: named wrappers/targets. | Wrapper identity **VERIFIED** statically. | **UNKNOWN**; no native AE lock/unlock demonstration. |
| `ShutterTool.SetTv`, `SetExpTime`, `GetCurTv`, `GetCurExpTime`, `CheckTv`, `CheckExpTime` | Function map §3, all under the `ShutterTool` name. | Named bindings **VERIFIED** statically; units, API layer and context unverified. | **UNKNOWN**, including read/query/check behavior from custom native code. |
| `MoveIrisWithAv`, `MoveIrisToAv`, `PutInNdFilter`, `PutOutNdFilter`, `OpenMShutter`, `CloseMShutter` | Function map §2: static service bindings with unresolved public/actuator-layer distinction. | Binding identity **VERIFIED** statically. | **UNKNOWN**; no exposure/aperture/ND/mechanical-shutter control demonstrated. |
| `MovieRecorder_StartRecording`, `SsMovieRec_ValidateAndStart`, `MovieRecorder_RequestSegmentSplit` and recording-limit configuration | Function map §4 and [recording-limits report §§1, 6](VIDEO001_RECORDING_LIMITS.md) describe internal code/state paths. | Recorded code paths **VERIFIED** as static findings; suitable external API contracts absent. | **UNKNOWN** for invocation, timing, completion, recording extension, rollover and file integrity. |
| `UIFS_StartMovieRecord`, `UIFS_StopMovieRecord` anchors | Function map §4 explicitly identifies string/table anchors and warns they are not callable code addresses. | String identity **VERIFIED** statically. | **UNKNOWN** callable entry/contract; a string is not a demonstrated start/stop API. |
| `PostLogicalEventToUI` / selected Canon UI-command dispatch | [UI-001C design review §4.1](UI001C_DESIGN_REVIEW.md) describes Canon's own event delivery, not a payload test. | Existing event-processing role documented; a custom shortcut's behavior **UNKNOWN**. | **UNKNOWN** for custom dispatch, mode safety and desired action; passive `GetKbdState` does not supply this. |
| Direct native `LCDMsg_Create` / `LCDMsg_Move`, live menu actions and overlay suppression | Loader/native split in R2–R4; [PORT-4E §§3.3–4](PORT4E_SYNCHRONOUS_FEATURE_FEASIBILITY.md) distinguishes static display and offline suppression candidate. | Additional UI functions **PLAUSIBLE** at a feature level; no demonstration in these five packages. | **UNKNOWN** beyond tested setters; no live navigation, suppression result or actionable setting. |
| `CreateTask`, `ExitTask` and any deferred custom callback | [PORT-4C §§5, 8–9](PORT4C_MEMORY_OWNERSHIP_LIFETIME.md): task/lifetime gates missing and termination-entry claims conflict. | Proposed integration **PLAUSIBLE** only as a direction. | **UNKNOWN**; none created a task/callback. Outside the demonstrated call-lifetime envelope. |

The named candidates are an inventory of existing evidence, not an investigation queue. Other internal functions in the movie map, such as frame-limit checks, warning/error handlers and task/queue setup, are likewise static findings; they are not additional demonstrated short-call interfaces.

## 5. What the strongest evidence actually establishes

**Most complete demonstrated primitive:** H5 combines native input reads, bounded sleeping/resumption, local computation, text/color setters and clean return within the borrowed task. Final text is rendered later by Canon. It does not run custom code after return or show interactive visual feedback during the sample window.

**Most clearly attributable API effect plus return:** H2 displayed both a return-confirmation banner and a string written only by the native setter after its pre-initialization. R2 expressly separates those two output paths. That supports text-setting callability more strongly than merely seeing a loader-generated PASS line. It still applies only to the tested setter/handle/context.

**Strongest UI behavior:** H3 displays three static lines in two colors after a Playback→Shooting transition. The “>” and “Settings” strings are decoration; there was no selection, command dispatch or settings change. A retained Canon descriptor is data, not a continuing native menu.

**Input-evidence boundary:** H5 reports UP in two runs plus a negative control; DOWN/LEFT/RIGHT/MENU/DISP/PHONE/VIDEO are single owner observations. SET, shutter half/full, playback and power were not mapped by these observations. Active-low interpretation is supported by baseline/differences, but [UI-001C review §1](UI001C_DESIGN_REVIEW.md) rejects describing cumulative XOR measurements as universal polarity/edge proof. Reading the VIDEO key is **not** invoking a recording API. Seeing stock AF or photography still work afterwards is a health observation, **not** native AF/exposure control.

Thus **no verified direct capability relates to controlling AF lock, focus mode, exposure or recording behavior**. The relationship is indirect only: a display could explain a stock workflow, and a passive sampler can observe selected switches. Neither changes the associated camera function.

## 6. Missing evidence for actual control and safe one-shot effects

| Area | Missing evidence / resulting boundary |
|---|---|
| AF lock and focus mode | Supported interface layer and signature; registration, camera-mode/Servo/MF and lock preconditions; allowed caller context; return versus operation completion; effect/state lifetime across script exit and mode changes; unlock/reversal/error behavior. Native control **UNKNOWN**. |
| Lens movement / exposure | Units, ranges, actuator state, timing and interlocks; completion/error handling; Canon synchronization and ownership; proof that a getter/checker is safe in this context. A named binding does not establish a safe movement, query or exposure action. |
| Recording start/stop or limit control | A supported entry/contract from this task context; safe timing and active-recording invocation; initialization ordering; completion and cleanup. Existing static evidence says recording startup reinitializes limits, defeating an assumed pre-start change. A valid lasting Canon configuration is **UNKNOWN**. |
| Extended recording | Runtime correspondence of recorder data, variable-bitrate/size margin, actual rollover/MP4 integrity, thermal/battery/storage stop linkage, finalization and failure behavior. [PORT-4E §3.1](PORT4E_SYNCHRONOUS_FEATURE_FEASIBILITY.md) and the [VIDEO-001A-0 review §6](VIDEO001A0_CLAUDE_FINAL_REVIEW.md) retain these limitations. Offline review or SD deployment is not a hardware result. |
| Actionable UI | An actual command handler and observed result; selection/confirmation semantics, debounce/event consumption or safe coexistence; live feedback; dismissal, repeat use, descriptor cleanup and pool pressure. None is supplied by static labels plus passive key reads. |
| Any short-call expansion | Borrowed-stack headroom and worst-case duration; reentrancy/mode/lock rules; argument copying versus retained pointers; queued completion, failure and recovery. Straight-line code or a returned sentinel is not proof of all effects or a time bound. |
| Retention / tasks | All five payload buffers were explicitly freed after return (PORT-4C E1–E5). PORT-4D establishes no allocator owner attribution, but script-teardown/mode lifetime remains **UNKNOWN**. Canon message retention does not satisfy G6 for native-owned memory. |

The full original objectives are not proved impossible. The evidence does not supply their needed control contracts. This inventory stops at **UNKNOWN** and does not propose a way around them.

## 7. Smallest useful function and recommended next decision

**Smallest evidence-supported function:** display one fixed informational message and return, leaving Canon to render its copied text in the already observed transition. H2 supports that capability directly; H3 supports multiple lines if needed. The display mechanism is **VERIFIED** for the tested text. Turning it into a useful stock-workflow reminder is **PLAUSIBLE**; new content/package, lifecycle and user benefit remain unvalidated. No task, custom callback or retained custom buffer is established or required by that demonstrated copied-text behavior.

An optional one-shot keyboard snapshot is a **VERIFIED diagnostic capability**, but adds no camera control. “AF lock shortcut” or “recording unlock” is not an evidence-supported label for either function. If “useful function” means an actual focus, exposure, recording or selected-settings action, **none has been found; the smallest such action is UNKNOWN**.

**Recommended next decision:** decide whether an informational-only helper satisfies a worthwhile minimum. If yes, the next milestone can be a documentation-only acceptance/evidence table for one existing stock AF-lock workflow reminder, with the exact stock source/page and its Servo limitation. If not, record that current evidence does not support an actionable minimum and stop. Neither branch authorizes implementation, ROM research, new tests, hardware or deployment; any later scope must be decided separately.

Warm-restart IRQ/SD blockers and native residency/G6 uncertainty remain unchanged. No classifier-stopped script-teardown, IRQ enumeration or SD write-site investigation was resumed or reframed. Historical task plans, “ready” labels and recovery assumptions do not authorize new work. Normal post-test shutdown and canaries are useful bounded evidence, not general safety guarantees.

Exact next command (read-only handoff):

```sh
cat /Users/avp/Project/g3x-lite/docs/PORT4F_VERIFIED_NATIVE_CAPABILITIES.md
```

## 8. Source provenance

All local sources were retrieved from the working tree on **2026-10-25**. H1/H2 observations are dated 2026-10-17; H3–H5 are dated 2026-10-18. Their documents identify the exact tested payloads/loaders; no executable was read or rehashed here. The underlying ROM identity is recorded there as SHA-256 `9911855772e433c877a9914f16d3735e15a48ca63352633e8f10364182912578`; it was not checked here. Local document hashes below identify the actual evidence, including untracked reports. No matching public revision is asserted for dirty/untracked files.

The existing [RESEARCH_LOG E008/E023](RESEARCH_LOG.md) and [PORT-4E §7](PORT4E_SYNCHRONOUS_FEATURE_FEASIBILITY.md) carry these inherited external locators. **No external source was newly fetched**:

| Exact external locator | Recorded retrieval/version | What it supports |
|---|---|---|
| [Canon G3 X user guide](https://gdlp01.c-wss.com/gds/3/0300019293/02/psg3x-cu2-en.pdf) | 2026-10-16; pp. 86, 91, 93 (AF/MF), 212–213 (movie limits) | Stock user capabilities/restrictions; no native call contract. |
| [G5 X CHDK wrappers](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/platform/g5x/wrappers.c) | 2026-10-16; r5491, commit `21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6` | Comparable-camera MF source pattern and focus-move caveat; no GM1.10C call demonstration. |
| [CHDK name/signature source](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/tools/finsig_thumb2.c) | GM1.10C function map cites r5491 at the same commit; local map read 2026-10-25; no new external retrieval | Corroborates name roles, not G3 X addresses, runtime behavior or safety. |

| Local source (state/handoff are pre-edit) | Reviewed SHA-256 |
|---|---|
| [AGENTS.md](../AGENTS.md) | `175efb8c0313ef3055a0e987f72f7ffaa593270ffd0b20da5ec07d8b2f361a7d` |
| [README.md](../README.md) | `b26a04b134888ac4184485a6c7545c62913dc09eb320d82b887a1af29ebdb31d` |
| [docs/SAFETY.md](SAFETY.md) | `c50f25b07500a844a374193b839028ca82de6007e6778eeb3a04049ffaaaa30d` |
| [docs/RESEARCH_PLAN.md](RESEARCH_PLAN.md) | `9a06e7e4769d83aeea1d61749f324e29117b01894f303748c5b266c16a139097` |
| [docs/PROJECT_STATE.md](PROJECT_STATE.md) | `1224d3828a106c0946228bbb883e86263391c8b7575266c7695b513d18f046c7` |
| [docs/HANDOFF.md](HANDOFF.md) | `eefd01bfff708c1630e345dd58ecc7f2ba3ec23912fc8add0887911419c7eba7` |
| [docs/PORT4E_SYNCHRONOUS_FEATURE_FEASIBILITY.md](PORT4E_SYNCHRONOUS_FEATURE_FEASIBILITY.md) | `4e7afd3c4ae886251c10f8642588cd88de06d859afc3a226872e7f246e54917d` |
| [docs/PORT4C_MEMORY_OWNERSHIP_LIFETIME.md](PORT4C_MEMORY_OWNERSHIP_LIFETIME.md) | `9be1a52eb489ef89e69d6819e38957431d813d4671a673b7a99d25a516813949` |
| [docs/PORT4D_G6_ALLOCATION_OWNERSHIP_AUDIT.md](PORT4D_G6_ALLOCATION_OWNERSHIP_AUDIT.md) | `f4e83318f23190cf0587b4eb2fea15689502ebc7958c3c0b941e324c9198b45d` |
| [docs/BOOT001A_HARDWARE_RESULT.md](BOOT001A_HARDWARE_RESULT.md) | `9f804b7a59ee3b1e61894b14ade8bce57fbbcfed612124d2df84b6fed8c4c99c` |
| [docs/BOOT001B_DIAG_HARDWARE_RESULT.md](BOOT001B_DIAG_HARDWARE_RESULT.md) | `738fcde1e502261fb6578a36657f48026b2ccff22d3aa6c8dc856e2e99062bcc` |
| [docs/UI001A_HARDWARE_RESULT.md](UI001A_HARDWARE_RESULT.md) | `40b606fc32426995835c269a11e7ffa7e81fb8404ff20d79e7db0e767ba965f7` |
| [docs/UI001B0_HARDWARE_RESULT.md](UI001B0_HARDWARE_RESULT.md) | `2734da34b08625e189e3c576957606cd0470d81f78bb3ffecffb34250088ebab` |
| [docs/UI001B1_HARDWARE_RESULT.md](UI001B1_HARDWARE_RESULT.md) | `8359dd1ecfff480660b71dafec1a7a19c7920e261ac19062a2601bad8ac47cb3` |
| [docs/BOOT001A_FINAL_DELTA_REVIEW.md](BOOT001A_FINAL_DELTA_REVIEW.md) | `1829b6ca3db8876cb0e8109f0d36a1715f80de501122d55174aa8c97a713a897` |
| [docs/BOOT001B_DIAG_FINAL_REVIEW.md](BOOT001B_DIAG_FINAL_REVIEW.md) | `a6f1b53ab8b892ae26b14abc976279917eb24eb9d5eaadcc075a4cfdc0cb4272` |
| [docs/UI001A_FINAL_REVIEW.md](UI001A_FINAL_REVIEW.md) | `9e4a66f9ac7f53db84aed2696fd6ac523707f3fb9eca2920f7f7f4e97619d4b3` |
| [docs/UI001B0_GEMINI_INDEPENDENT_REVIEW.md](UI001B0_GEMINI_INDEPENDENT_REVIEW.md) | `1bcb825383e686c7c8cbd07dae6ea77e00a28cbe78863f54b0bcf7eb5b989356` |
| [docs/UI001B1_FINAL_REVIEW.md](UI001B1_FINAL_REVIEW.md) | `3fb72238147292be2e5321f7a759563e24c8fd48393b74adc24233a9535bfb01` |
| [docs/BOOT001_MINIMAL_POC_DESIGN.md](BOOT001_MINIMAL_POC_DESIGN.md) | `45c0285238e9777c77459ec6f78c74c22ac17fdb267bd5a08c09ac4ad2645067` |
| [docs/GM110C_FUNCTION_MAP.md](GM110C_FUNCTION_MAP.md) | `fd5d135ec850b303574365777405d4b0b3fddf431f321e34263afd6ec9a5dba7` |
| [docs/RESEARCH_LOG.md](RESEARCH_LOG.md) | `49c186a612505f3fbbd8285fd99a20460fba0751b4ed764682e00576c8dc80b4` |
| [docs/UI001C_DESIGN_REVIEW.md](UI001C_DESIGN_REVIEW.md) | `2543bd2f01b9993f3e10bbd6ab7d2ea10ceea297acca33a29b450fc133d382a0` |
| [docs/VIDEO001_RECORDING_LIMITS.md](VIDEO001_RECORDING_LIMITS.md) | `a1873bd0ba10f25f6b72d7e59e71d2547f27b9a0589876741e0521dbef2ce502` |
| [docs/VIDEO001A0_CLAUDE_FINAL_REVIEW.md](VIDEO001A0_CLAUDE_FINAL_REVIEW.md) | `0a88fa7760b6184e5cdd73d97cc7b86d8c9fffa9e38bfab450b323ebdbaf9f26` |

Other existing design/test-plan documents were searched only for documented API names and context: `BOOT001A_TEST_PLAN.md`, `BOOT001A_FINAL_REVIEW.md`, `BOOT001A_BLOCKER_REMEDIATION.md`, `UI001A_STATIC_MENU_DESIGN.md`, `UI001B0_TEST_PLAN.md` and `UI001B1_TEST_PLAN.md`. Their historical instructions were not executed. The direct-call classifications rely on H1–H5 and R1–R5.

Only this report and prepended PORT-4F entries in PROJECT_STATE/HANDOFF were written. The dirty worktree is intentional: pre-existing work is preserved, and this task prohibits commits/pushes. No staging, cleanup or phase transition occurred.
