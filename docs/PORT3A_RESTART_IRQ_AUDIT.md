# PORT-3A: Adversarial warm-restart IRQ audit (GM1.10C)

Date: 2026-10-25 · Agent: Claude Code · READ-ONLY.

**Verdict: `NOT_PROVEN_SAFE`. No mitigation is justified by ROM evidence.**

## Scope and sources

- ROM: `firmware/dumps/GM1.10C/PRIMARY.BIN` (SHA-256 `99118557…12578`), mapped as in `docs/RESTART_IRQ_PENDING_AUDIT.md`.
- Builds on `docs/RESTART_IRQ_PENDING_AUDIT.md` (RESTART-IRQ-1) and `docs/RESTART_SD_HOST_AUDIT.md`. Addresses that were already pinned are pinned in `tests/test_restart_irq_audit.py`.
- **Prototype state at audit time:** `boot_prototype.c` `task_Startup_my` now contains the RESTART-SD-1 `SD1stInit` creation, gated by `sub_fc05c4e0(0)` and calling `blx sub_fc31b1f4`. Another agent applied that change. It is not reviewed here, except where it touches IRQs (F10).

Classification: **V** = verified from ROM bytes · **P** = plausible · **U** = unknown.

## 1. Findings

| # | Finding | Evidence | Class | Impact on continuation safety | Unresolved precondition |
|---|---|---|---|---|---|
| F1 | The interrupt controller is Canon's `0xD401xxxx` block, not an ARM GIC. IRQ entry reads the active id from `0xD4011000` and writes it back to `0xD4011010` after dispatch. | `0xFC05B6F2: ldr r0,=0xD4011000; ldr r0,[r0]`; `0xFC05B70E: ldr r0,=0xD4011010; str r4,[r0]`; vector slot `0xFC05B4AC` = `0xFC05B6A9` | V | Earlier GIC-based reasoning (PORT-2C §2.1) does not apply. | — |
| F2 | Handler table at `0x0003F4F4` (8 bytes per id) is zeroed by `boot()` (BSS `0x3F4F4..0x3489B4`). | Literal `0xFC0BAE1C`; dispatcher `0xFC0BAD3C`; zero loop at `0xFC020068..78` (prototype identical) | V | After restart, every id has no handler until it is re-registered. | — |
| F3 | An unregistered id causes a hard hang. | `0xFC0BAD86` printf "Illegal inter"; `0xFC0BAD92` → `0xFC084BA4(0x40,2)`; `0xFC084BBC: b .` (hook `0x802C` = 0 in ROM data) | V | One stray IRQ at the wrong time hangs the camera in IRQ mode. | — |
| F4 | IRQ masking across the handoff: CPSR.I is set by the pre-DISKBOOT jump, the loader adds `cpsid if`, and nothing unmasks until the first task's wrapper. | `0xFC0D9CA2` → `0xFC31BEFC` → `0xBFE14FE6` → `0xFC127B3C` (`orr #0x80`); loader `cpsid if`; wrapper `0xFC267BE6` (`bic #0x80`) | V | No IRQ is taken during the relocation, recopy, BSS zero or kernel init. | — |
| F5 | Controller init runs again on the restart path, as the kernel's first action and before any unmask. | `0xFC05B448` / prototype `blx sub_fc31b408` → `0xBFE10F79`; `0xBFE10F80` → `0xFC05C570`: `movw r0,#0x1B0; bl 0xFC05E500` | V | The pending/bank state is touched identically in cold boot and restart. | — |
| F6 | Init writes, in order: `0xFFFFFFFF` → `0xD4010000+16i+0xC` (i<16); `1` → `0xD401010C`; `1` → `0xD4011200`; `[0x8064]=0x1B0`. | `0xFC05E4DC..0xFC05E4F2`, `0xFC05E50A..0xFC05E510` | V (writes) | What each write does in hardware is **U**. | Register semantics |
| F7 | Per-line id registers: write id → `0xD4011010` (enable) or `0xD4011018` (disable), bounded `0 < id < [0x8064]`. | `0xFC05E532: str r0,[r4,#0x10]`; `0xFC05E556: str r0,[r4,#0x18]`; same-id pairing `0xFC05C5F4/5FC` vs `0xFC05C770/778` | V (access); P (meaning) | Nothing on the restart path writes `0xD4011018` in bulk. If F6 does not clear enables, lines enabled before `StartDiskboot` stay enabled. | Semantics of F6 |
| F8 | Bank `+4` behaves like a "pending" read: the kernel time read adds one tick if bit(0x1B) is set. | `0xFC05E59E: ldr r0,[r0,#4]`; `0xBFE148E2: movs r0,#0x1B; blx 0xBFE13D6C` | P | Suggests the F6 `+0xC` write clears pending (same bank layout). This is not proof. | — |
| F9 | Bank `+8`/`+0xC` per-id writers form a pair (set/clear of an attribute that is **U**). | `0xFC0D9AA0`, `0xFC0D9B42`; both used on id 0x2A at `0xFC12EC9E` / `0xFC12ECA4` | V (writes) | The `+0xC` write may mask lines **or** clear another attribute (routing/wake). | Semantics |
| F10 | First unmask is at the very start of the first task. Only tick `0x1B` is re-registered by then (`0xBFE1149C` → `0xFC05C65E..0xFC05C68C`). All other handlers return only as `task_Startup_my` re-runs driver init: `sub_fc0d0150`, `sub_fc05ba34`, `sub_fc05bb94`, `sub_fc418eec`, `SD1stInit`, and later calls. | Kernel init order (`0xBFE10F78..`); RESTART-SD-1 §6 | V (order) | This window exists in both stock cold boot and restart. In the restart, the controller is **not** in its reset state while it is open. | Which lines were enabled at `StartDiskboot` |
| F11 | Driver IRQ API: register + enable (`0xBFE14F00`, ROM veneer `0xFC31BDBC`), register only (`0xBFE14F2E`, `0xFC31B4B4`), disable (`0xBFE14F56`, `0xFC31BDAC`). All check `0 < id < 0x1B0`. | `0xBFE14F0A: cmp.w r4,#0x1b0`; veneer literals `0xFC31BDC0` / `0xFC31B4B8` / `0xFC31BDB0` | V | These are the routes by which first-boot drivers enabled lines that can survive. | Full caller and id list **not enumerated** |
| F12 | Per-line config at `0xD4013000+4*id` is written by drivers directly (for example `0xFC12EC98: str 0x1C → [0xD4013000+8]`) and by `0xFC05E564`. Init (F6) does not touch it. | Literal sites `0xFC05E5B8`, `0xFC0D766C`, `0xFC0F22DC`, `0xFC0F2708`, `0xFC12E990`, `0xFC12EDB0`, `0xFC447E14` | V (writes); U (meaning, e.g. priority/trigger) | Config from the first boot persists. Drivers rewrite their own on re-init. Stale config only matters for lines that are still enabled. | Semantics |
| F13 | `0xD4012000+4*idx` (idx<12) has a setter at `0xFC0D9BE6`, reached via `0xFC0FC3B8 b.w`. | Literal `0xFC0D9C98` | V (writes); U (meaning, caller context) | Unassessed persistent IC state. | — |
| F14 | A cold-boot-only write the restart skips: boot ROM `0xFC000068: bl 0xFC000444`, which writes `0` → `0xD4020040` and `0` → `0xD4020000`. Callers traced back to `0xFC003A8C`, not to the reset vector. | `0xFC000444: 0249 0020 0864 0860` | V (writes); P (cold-boot-only); U (block identity) | The restart and Canon's own `0xFC0D03E8` path both enter at `0xFC020000` or later and skip this. Effect **U**. | Identity of `0xD4020000` |
| F15 | Canon's restart routine `0xFC0D03E8` masks IRQ and calls bulk writer `0xFC0D9C52` (`0x0FFFFFFF` → `+0xC`) before `bx 0xFC020001`. Its only static caller uses mode 7, which returns without jumping. | `0xFC0D041A..0xFC0D0438`; `0xFC3835F8: movs r0,#7` | V (code); U (reachability of the jump) | Suggests Canon treats `+0xC` as a pre-restart quiesce. Not proof. | Semantics, reachability |
| F16 | No IRQ is in service at handoff. `StartDiskboot` runs in task context and IRQ entry finishes (with write-back to `0xD4011010`) before returning to the task. | `0xFC05B70E`; nesting counter `0x8160`, which is restored to 0 by the low-RAM recopy | P | An "active" state left in the controller is unlikely. | Controller in-service semantics **U** |

**Counterexamples to earlier assumptions:**
- "GIC distributor retains lines" (wrong model, F1).
- "DryOS handler is active" (false, F2/F3).
- "Kernel init clears enable masks" (unproven, F6/F7/F9).
- "Restart repeats the cold boot" (false for the boot-ROM write, F14).

## 2. Cold boot vs restart

| Step | Cold boot | CHDK restart | Same? |
|---|---|---|---|
| Boot ROM `0xFC000000..` (incl. F14) | runs | skipped | **No** |
| CPU I/F at `0xFC02000C` | masked by reset | masked by loader `cpsid if` | yes |
| `0xFC02000C..0xFC02007A` (vectors, clock gate, 3 copies, BSS zero) | ROM | `boot()`; same constants, only the final branch target differs | yes |
| `sub_fc05b3c8` | heap base `0x003489B4` | `new_sa`; witness | IRQ-neutral |
| Kernel init incl. F5/F6 | from the controller's reset state | from the controller's retained state | **No** (inputs) |
| First unmask (F10) | all lines reset-disabled (**P**) | lines from the first boot possibly enabled (**U**) | **No** |
| `task_Startup` | includes `StartDiskboot` | omits it; adds `SD1stInit` creation | IRQ-neutral (driver re-init order kept) |

## 3. Risk matrix (prioritized)

| Rank | Risk | Likelihood | Severity | Basis |
|---|---|---|---|---|
| 1 | A line enabled in the first boot asserts in the F10 window, so its id has no handler and the camera hangs (F3) | U (Medium) | High (hang, battery pull) | F2, F3, F7, F10 |
| 2 | Pending bit latched before the restart is not cleared by F6 | Low–Medium (P: F8 suggests it is cleared) | High (same hang) | F6, F8 |
| 3 | Stale per-line config (F12/F13) on a surviving line changes priority/trigger | U | Medium | F12, F13 |
| 4 | Cold-only `0xD4020000` init skipped (F14) | U | U | F14 |
| 5 | In-service state left in the controller | Low | High | F16 |

## 4. Mitigation

**None proposed.** Every candidate requires one of the following:
- writing the F6/F9 registers with unproven semantics;
- a bulk `0xD4011018` disable sequence that the ROM never performs;
- calling `0xFC0D9C52`, whose effect is unproven and whose restart-path reachability is unproven (F15).

The RESTART-IRQ-1 trial of `0xFC0D9C52` was reverted for these reasons.

## 5. Strongest unresolved blocker

There is no ROM proof that anything between `StartDiskboot` and the first task's IRQ unmask (`0xFC267BE6`) disables the per-line enables set during the first boot. Specifically, the semantics of the `0xD4010000+16i+0xC` init write (F6) are unproven, and the set of lines enabled at `StartDiskboot` (F11 caller and id list) is unknown. Combined with F2/F3, a single surviving, asserted line hangs the camera.

**Closing it needs one of:**
1. Cited and vetted register documentation for this controller.
2. A full enumeration of F11 callers reached before `StartDiskboot`, each shown to leave its device quiescent.
3. Approved hardware observation (NO-GO).

## 6. Changes

- Added this document.
- No code, test, `candidate_port2a/`, production or MMIO changes.
- No builds were run. The prototype ELF was only read with objdump.
