# PORT-3B: IRQ controller register semantics audit (GM1.10C)

Date: 2026-10-25 · Agent: Claude Code · Read-only.

**Final classification: `UNKNOWN`.**

## Evidence base and labels

- Evidence comes only from what was already established in `docs/RESTART_IRQ_PENDING_AUDIT.md` (RESTART-IRQ-1) and `docs/PORT3A_RESTART_IRQ_AUDIT.md`. ROM bytes for those addresses are pinned in `tests/test_restart_irq_audit.py`.
- No new tracing, MMIO access or builds were done.

Labels:
- **PROVEN-W/R:** the ROM provably performs this access (address, value, order).
- **INFERRED:** semantics suggested by usage pattern only.
- **UNSUPPORTED:** an assumption with no ROM support.

Rule applied: a value written during initialization is **not** taken to mean "disable" or "clear".

## 1. Register evidence table

| Register | Proven access | Code | Inferred semantics (basis) | What is NOT supported |
|---|---|---|---|---|
| `0xD4011000` | Read in IRQ entry. The value is used as the handler-table index (`0x3F4F4 + id*8`) and passed to the dispatcher. | `0xFC05B6F2..F6`; `0xFC0BAD52..58` | Active/current line id: **P (strong)**, because the value is used as an id. | That the read acknowledges or masks the line (**U**). |
| `0xD4011010` | (a) The IRQ entry writes back the same id after dispatch. (b) `0xFC05E51C(id)` writes `id` (bounded `0<id<[0x8064]`), then `dsb`, then reads `0xD4011200`. | (a) `0xFC05B70E..10`; (b) `0xFC05E530..38` | Per-line enable by id: **P**. It is used after registering the tick handler (`0xFC05C674` → `0xFC05C68C`) and is paired with `0xD4011018` on the same ids. | Distinguishing "enable" from "end-of-interrupt / re-arm": both fit (a). Whether (a) re-enables a line that the read masked is **U**. |
| `0xD4011018` | `0xFC05E540(id)` writes `id` (same bounds, `dsb`, read `0xD4011200`). | `0xFC05E554..5C` | Per-line disable by id: **P**. Same ids as enable: `0xE7`/`0x16D` enabled at `0xFC05C5F4/5FC`, disabled at `0xFC05C770/778`. Exported next to register/unregister (`0xBFE13E10`). | — |
| `0xD4011200` | Read after every by-id and bank access; written with `1` once during init. | `0xFC05E4FA`, `0xFC05E50A..0C`, `0xFC05E538`, `0xFC05E55C` | Read-back for write ordering, plus a global enable at init: **P (weak)**. | Any specific meaning (**U**). |
| `0xD4010000 + 16*(id&15) + 4`, bit `id>>4` | Read only. | `0xFC05E58A..A6` | Per-line pending/raw status: **P**. The kernel time read checks line `0x1B` (system tick) and adds one 10 ms tick if set (`0xBFE148E2..EC`). | Whether it is raw or masked status; whether reading clears it (**U**). |
| bank `+8`, bit `1<<((id>>4)&31)` | Per-id single-bit write. | `0xFC0D9AA0`; used at `0xFC12EC9E` (id 0x2A) | Paired set/clear attribute: **P**. | Which offset sets or clears, and which attribute (**U**). |
| bank `+0xC`, per id | Per-id single-bit write. | `0xFC0D9B42`; used at `0xFC12ECA4` (id 0x2A) | Counterpart of `+8`: **P**. | As above (**U**). |
| bank `+0xC`, bulk | `0xFFFFFFFF` × 16 banks at init; `0x0FFFFFFF` × 16 in `0xFC0D9C52`. | `0xFC05E4DC..F0`; `0xFC0D9C52..8A` | — | **That it clears enable, clears pending, or does anything specific: UNSUPPORTED.** |
| `0xD401010C` | Written with `1` at init. | `0xFC05E4F0..F2` | — | Meaning (**U**). It matches the bank-16 `+0xC` slot, but ids map only to banks 0..15. |
| `0xD4012000 + 4*idx` (idx < 12) | Setter writes a caller-supplied value. | `0xFC0D9BE6..`; reached via `0xFC0FC3B8 b.w` | — | Meaning and caller context (**U**). |
| `0xD4013000 + 4*id` | `0xFC05E564(id, cfg)` writes `(cfg[0]&1)<<2 \| (cfg[1]&1)<<3`. Drivers also write it directly (e.g. `0xFC12EC98: 0x1C → +8`). | `0xFC05E564..84`; literal sites listed in PORT-3A F12 | Per-line configuration: **P**, because it is set before enable for the tick path (`0xFC05C686` cfg for id 0x1D, then enable 0x1B). | Priority vs trigger vs routing (**U**). |
| Active / in-service register | None identified. | — | — | Any in-service state or its reset (**U**). |

**Weak counter-evidence** against "`+0xC` = enable-clear":
- Per-line enable/disable already exists by id (`0xD4011010/18`).
- A *separate* set/clear pair exists on `+8/+0xC` and is applied to the same id 0x2A.
- If `+8/+0xC` were also enable controls, the controller would have two independent enable interfaces. That is possible but unexplained.
- This weakens, but does not refute, the enable-clear reading. It is equally compatible with `+0xC` clearing pending, routing or wake state.

## 2. Distinguishability of register classes

| Class | Distinguished by ROM evidence? |
|---|---|
| Enable / disable | Partly. The by-id `0xD4011010/18` pair is **P**. The role of the bank interface is **U**. |
| Pending / acknowledge | Pending read `+4` is **P**. Acknowledge (read side effect of `0xD4011000`, or write `0xD4011010`) is **U**. |
| Active / in-service | **U.** No register is identified. |
| Priority / configuration | `0xD4013000` per-id config is **P**. Its field meaning is **U**. `0xD4012000` is **U**. |

## 3. Sequence before the first unmask (`0xFC267BE6`)

All steps below are PROVEN-W/R and are identical on cold boot and restart.

1. Kernel init `0xBFE10F78`, first call `0xBFE10F80` → `0xFC05C570` → `0xFC05E500(0x1B0)`:
   1. `+0xC` ← `0xFFFFFFFF` for banks 0..15;
   2. `0xD401010C` ← 1;
   3. `dsb`;
   4. read `0xD4011200`;
   5. `0xD4011200` ← 1;
   6. `[0x8064]` ← `0x1B0`;
   7. `dsb`;
   8. read `0xD4011200`.
2. Kernel init `0xBFE1149C` → `0xFC05C65E`:
   1. register tick handler (`0xFC0BADBC`, id 0x1B);
   2. `0xD4013000+4*0x1D` config;
   3. `0xD4011010` ← `0x1B`.
3. First task dispatched with CPSR `0xF3`. Task wrapper `0xFC267BE6` clears I.

**Not written before the unmask:**
- `0xD4011018` (no bulk disable);
- bank `+8`;
- `0xD4012000`;
- `0xD4013000` for any line other than 0x1D.

**Consequence:** whether the first-boot per-line state reaching `0xFC267BE6` is cleared depends entirely on step 1.1–1.5, whose semantics are **U**.

## 4. Evidence gaps (not retried)

- **PORT-3A:** enumerating the callers and line ids of the driver IRQ API (`0xFC31BDBC` / `0xFC31B4B4`) was **stopped by the safety classifier**. The lines enabled at `StartDiskboot` remain **U**.
- **RESTART-SD-1:** enumerating the SD driver's register write sites was **stopped by the safety classifier**. That is not IRQ-specific, but SD-line state is **U**.
- **Cold-boot-only write:** `0xD4020000/0xD4020040` ← 0 (PORT-3A F14). Its block identity is **U**.

## 5. Dependency graph of unresolved preconditions

```
SAFE_WARM_RESTART_IRQ
 └─ no first-boot line asserts with an empty handler slot after 0xFC267BE6
     ├─ (A) first-boot per-line ENABLE state is cleared before unmask ............ U
     │    ├─ (A1) bank +0xC bulk write clears enable ............................. U
     │    ├─ (A2) 0xD4011200 / 0xD401010C writes reset enable .................... U
     │    └─ (A3) no other enable interface retains state (+8 role, 0xD4012000) .. U
     ├─ (B) first-boot PENDING state is cleared before unmask ..................... U
     │    ├─ (B1) +4 is the pending status ...................................... P
     │    └─ (B2) bulk +0xC write clears what +4 reports ......................... U
     ├─ (C) no line is left in service (active state) ............................ U
     │    └─ (C1) no IRQ in progress at StartDiskboot (task context) ............. P
     └─ (D) if (A) fails: every surviving enabled line is quiescent ................ U
          └─ (D1) list of lines enabled at StartDiskboot ........ U (classifier-blocked gap)
```

## 6. Final classification

| Question | Classification |
|---|---|
| ROM performs the init writes (values, order, before unmask) | **VERIFIED** |
| `0xD4011000` = current line id | **PLAUSIBLE** |
| `0xD4011010` / `0xD4011018` = per-line enable / disable | **PLAUSIBLE** |
| bank `+4` = per-line pending status | **PLAUSIBLE** |
| bank `+0xC` bulk `0xFFFFFFFF` semantics | **UNKNOWN** |
| `0xD401010C`, `0xD4011200`, `0xD4012000`, `0xD4013000` semantics | **UNKNOWN** (config role of `0xD4013000`: PLAUSIBLE) |
| Warm-restart IRQ safety | **UNKNOWN** |

**Strongest defensible finding:** the ROM proves *what* is written and *when*: one bulk `+0xC` write per bank, `0xD401010C`/`0xD4011200` ← 1, then tick setup, all before `0xFC267BE6`. It also proves a by-id enable/disable interface exists that is never applied in bulk. It does not prove that any pre-unmask write clears per-line enable or pending state.

**Exact remaining blocker:** precondition (A), and failing that (D). Specifically:
1. the hardware meaning of the bank `+0xC` write at `0xFC05E4E8` (and `0xD401010C`/`0xD4011200` at `0xFC05E4F2`/`0xFC05E50C`); and
2. the list of lines enabled at `StartDiskboot`. That enumeration was blocked by the classifier and was not retried.

Neither can be resolved from the ROM evidence available. The conclusion stops at UNKNOWN.

No mitigation proposed. No code, test, firmware, candidate or production files changed.
