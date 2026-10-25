# PORT-5B — Ranma G3 X historical boot comparison

Date: **2026-10-25 (Asia/Seoul)**. Analyst: Claude Code. Workspace: `/Users/avp/project/g3x-lite`, branch `docs/port4-documentation-consolidation`, HEAD `57968eb` (dirty/untracked work preserved).
Scope: read-only comparison of ranma's patch with our existing prototype and documents.
- The patch was **not** applied, dry-run or built.
- No ROM was disassembled. GM1.10C values come only from our existing prototype source and documents.
- No executable, firmware, loader or test file was modified. No camera, SD or hardware action.
- Upstream CHDK files were read as text from the public mirror `01luna/CHDK` to check provenance.

**Overall verdict: SOURCE RECOVERED. The prototype's boot skeleton is confirmed, the GM1.10E→GM1.10C mapping is not, and no blocker is resolved.**
- **Skeleton:** our GM1.10C prototype follows the same restart skeleton as ranma's GM1.10E source. The kernel-entry and heap-descriptor stages match nearly instruction for instruction.
- **Mapping:** the address correspondence is irregular, so no 1.10E value can be carried over mechanically.
- **Not resolved:**
  - The PORT-3/PORT-4 IRQ, SD and continuation blockers.
  - C residency (G6).
  - Hardware NO-GO.

This document **supersedes the NOT_FOUND result in [PORT-5A](PORT5A_RANMA_PORT_RECOVERY.md)**, now that the owner has supplied the file. PORT-5A's provenance chain is still valid and is relied on here.

## 1. Classification

- **SOURCE VERIFIED:** stated by the patch text at the cited patch line, or by a byte comparison performed here.
- **HISTORICALLY REPORTED:** ranma's forum statements ([PORT-5A](PORT5A_RANMA_PORT_RECOVERY.md)) or comments/TODOs inside the patch. These record what ranma believed or observed; they are not proof of behavior.
- **INFERRED:** follows from verified facts plus a stated premise.
- **UNKNOWN:** not established; stop here.

Patch line numbers ("P:n") refer to `g3x_110e.patch` as stored (9,277 lines; CRLF/LF mixed; numbering unaffected). Prototype references ("C:n") are `chdk-port/platform/g3x/sub/110c/boot_prototype.c`.

## 2. Artifact verification and inventory

| Item | Result | Status |
|---|---|---|
| Location | `/Users/avp/project/g3x-lite/g3x_110e.patch` (untracked, repo root). A byte-identical copy is at `~/Downloads/g3x_110e.patch`. | SOURCE VERIFIED |
| SHA-256 | `55927968545338c190100db97661ed4843b74b480c199af3cb643c00ccf1ccba`, which **matches** the expected value | SOURCE VERIFIED |
| Size | 336,714 B = 328.82 KiB, matching the forum display "328.82KB" (PORT-5A) | SOURCE VERIFIED |
| Type | `file`: unified diff, ASCII, CRLF/LF mixed. SVN `Index:` format. | SOURCE VERIFIED |

The diff contains 28 `Index:` entries. Twenty-seven have hunks; `platform/g3x/sub/110e/makefile.inc` (P:8570) is an empty new file.

| Path (patch line) | +lines | Role |
|---|---:|---|
| `loader/g3x/Makefile` (1), `blobs.S` (7), `entry.S` (24), `main.c` (37) | 1 / 12 / 8 / 62 | Loader: entry, core blob, copy + D-cache clean + jump |
| `platform/fi2.inc.txt` (104) | 5 | Adds an empty `d4g` FI2 key block (**modifies upstream**, base r5480) |
| `platform/g3x/Makefile` (117), `makefile.inc` (580) | 1 / 58 | Platform build values, memory placement |
| `platform/g3x/kbd.c` (123), `platform_kbd.h` (1053) | 130 / 20 | Keymap, `mykbd_task`, jog dial |
| `platform/g3x/lib.c` (258), `main.c` (504), `shooting.c` (1078), `wrappers.c` (9114), `platform_camera.h` (845) | 241 / 71 / 183 / 42 / 203 | Generic platform glue (forked from G5X, P:648) |
| `platform/g3x/notes.txt` (643) | 197 | Developer notes, memory map, issues |
| `platform/g3x/sub/110e/Makefile` (1266), `makefile.inc` (8570, empty) | 4 / 0 | Sub-platform build |
| `platform/g3x/sub/110e/boot.c` (1275) | 732 | **Boot chain and all task hooks** |
| `platform/g3x/sub/110e/filewrite.c` (2012) | 551 | `task_FileWrite` replacement (PTP remote capture) |
| `.../finsig_thumb2.log` (2568), `funcs_by_address.csv` (2934), `funcs_by_name.csv` (5752) | 361 / 2813 / 2813 | Generated signature-finder output for GM1.10E |
| `.../physw_bits.txt` (8572), `stubs_auto.S` (8629), `stubs_entry.S` (8722), `stubs_entry_2.S` (9063), `stubs_min.S` (9100) | 52 / 88 / 336 / 32 / 9 | Stubs (generated plus hand-found) |
| `tools/finsig_thumb2.c` (9161) | 76 (+2 −2 changed) | Sigfinder additions (**modifies upstream**, base r5480) |

The patch contains no binaries. It does contain historical MMIO addresses inside `#if 0` blocks and in the TricInitTask hook. These are recorded as text only, and none was investigated.

## 3. Provenance and base revision

| Question | Evidence | Status |
|---|---|---|
| SVN base revision | Both upstream-modified files carry `(revision 5480)`: P:106 and P:9163. In `svn diff`, that is the working-copy BASE revision. All new files show `(revision 0)`. | SOURCE VERIFIED |
| r5480 identity | Mirror commit `9a42137e185b87947fd73064ecd4f9bc3c83209c`, 2020-04-29T20:23:02Z, "ixus115_elph100hs: fix image distortion after using set_zoom", `git-svn-id …trunk@5480` | SOURCE VERIFIED (mirror) |
| Preimage check (text comparison, not `git apply`) | **r5480:** every hunk preimage matches exactly at its stated line: `fi2.inc.txt` @48 and `finsig_thumb2.c` @7, 439, 899, 4454, 4741. **r5491:** the `finsig_thumb2.c` hunk @439 has no match anywhere, and hunks @899, 4454 and 4741 match only at shifted lines (904, 4459, 4750). `fi2.inc.txt` is identical at r5479, r5480 and r5491. `finsig_thumb2.c` is identical at r5479 and r5480 but differs at r5491 (r5481, 2020-05-03, "exmem stubs related sigfinder changes", falls in between). | SOURCE VERIFIED |
| Relation to r5491/r5492 | Published 2020-05-11, between r5491 (2020-05-11) and r5492 (2020-05-15) (PORT-5A). The tree was **not** updated past r5480, so it is not an r5491 tree. | SOURCE VERIFIED |
| Timeline consistency | r5480 (2020-04-29) precedes ranma's first G3 X post (2020-05-04). | SOURCE VERIFIED |

**Base: CHDK trunk r5480.** The `Index:` headers state it, and the preimage check corroborates it. Our candidate is built on r5491 (`candidate_port2a/candidate_manifest.json`). The two bases differ by 11 trunk revisions, including the r5481 sigfinder change.

## 4. GM1.10E vs GM1.10C correspondence (document-to-document only)

The table compares values written in ranma's source with values written in our prototype and documents. No ROM was read, and every C value is only as good as the existing document it comes from.

| Role | GM1.10E (patch) | GM1.10C (ours) | Delta |
|---|---|---|---|
| RAM-code copy source | `0xfcec8574` P:1385 | `0xfcec854c` C:107 | −0x28 |
| TCM copy source | `0xfceef274` P:1397, P:2592 | `0xfceef24c` C:123 | −0x28 |
| Low-RAM data copy source | `0xfce91080` P:1413, P:2593 | `0xfce91058` C:134 | −0x28 |
| Copy destinations/ranges, BSS end | `0x010e1000–0x01107d00`, `0xbfe10800–0xbfe17419`, `0x8000–0x3f4f4`, BSS → `0x3489b4` (P:1386–1423) | identical (C:108–147) | 0 |
| ARAM-size literal location | `@0xfc5588b4` P:610 | `0xFC55888C` (110c makefile.inc) | −0x28 |
| `bzero`, kernel init, `dmSetup` | `fc31bfd4`, `fc31b430`, `fc418760` (P:1561, 1598, 1633) | `fc31bfac`, `fc31b408`, `fc418738` (C:203, 252, 289) | −0x28 |
| `j_CreateTask`, pre-startup calls | `fc31bbec`, `fc31b488`, `fc382cb4` (P:1717, 1707, 1710) | `fc31bbc4`, `fc31b460`, `fc382c8c` (C:365, 353, 356) | −0x28 |
| task_Startup calls (4 of 24) | `fc418f14`, `fc418f52`, `fc2a761e`, `fc3331c2` (P:1735, 1744, 1749, 1757) | `fc418eec`, `fc418f2a`, `fc2a75f6`, `fc33319a` (C:384, 404, 418, 426) | −0x28 |
| task_Startup calls (remaining 20), continuation | `fc0d0150 … fc0bb6fe`, `fc0d0126` | identical | 0 |
| Init-task strings (`"/_term"`, `"USER_MEM size checking"`, `"dmSetup"`, …) | `0xfc05b600`, `…610`, `…630` (P:1612–1668) | `0xfc05b604`, `…614`, `…634` (C:268–324) | **+4** |
| USER_MEM check words | `[0x80ec]` vs `[0x8074]+0x10` (P:1614–1618) | `[0x80f0]` vs `[0x8078]+0x10` (C:270–274) | **+4 (see F3)** |
| `"Startup"` string, heap-check constants, OS limits | `0xfc05b9a0`; `0x6ce000`, `0xb1fec`, `0x60e000`, `0xc0000`, `0x600014`; limits `0x22…0x2000` (P:1542–1596) | identical (C:180–245, 364) | 0 |
| `hook_CreateTask` (TCM) | `0xbfe14a3c` P:9045 | `0xbfe14a3c` ([PORT-0B stubs audit](CHDK_PORT0B_STUBS_AUDIT.md), value `0x2de9fe43`) | 0 |

- **SOURCE VERIFIED:** the E values exist in the patch exactly as listed.
- **INFERRED:** the E→C relation is **not uniform**:
  - Some regions are unchanged.
  - Many are −0x28.
  - The strings in one function are +4.
  - Every 1.10E address therefore needs independent 1.10C confirmation. "Same address" and "−0x28" are observations to test, not rules.
- **UNKNOWN:** the cause of the irregular differences (separately compiled builds is plausible, not shown).

## 5. Architecture comparison

| Topic | ranma GM1.10E (source) | Our GM1.10C prototype | Status / note |
|---|---|---|---|
| **Loader entry** | `entry.S`: `sp = MEMBASEADDR (0x8000)`, `bx my_restart` (P:28–36). `my_restart`: `check_compat()`, copy core to `MEMISOSTART`, D-cache clean (MVA or set/way), `bx MEMISOSTART+1` (P:47–101). **No IRQ masking, no I-cache invalidate.** | `main_prototype.c`: core copy to `0x003489B4`, boot witness, D-clean + invalidate, `dsb`/`isb`, **`cpsid if`**, jump | SOURCE VERIFIED. ranma's restart ran with whatever IRQ state DISKBOOT entry left. Ours deliberately masks IRQs per [RESTART_IRQ_PENDING_AUDIT](RESTART_IRQ_PENDING_AUDIT.md). |
| **Core placement** | `MEMISOSTART = ARAM_HEAP_START = 0x00c80000`, because `OPT_CHDK_IN_ARAM=1` (P:613–624) | `MEMISOSTART = 0x3489b4`, `OPT_CHDK_IN_ARAM` empty | SOURCE VERIFIED. **Fundamental difference** (F1). |
| **Canon heap shift** | `sub_fc05b3c9_my` uses the literal `0x003489b4` when `CHDK_NOT_IN_CANON_HEAP` is defined, else `new_sa` (P:1535–1540). Upstream r5480 `makefile.inc:214–215` defines `CHDK_NOT_IN_CANON_HEAP` under `OPT_CHDK_IN_ARAM`. **So ranma's build does not shift the Canon heap.** | Heap base shifted to `new_sa` (`0x00366C90` per manifest). Same 0x78-byte descriptor otherwise. | SOURCE VERIFIED (patch + upstream makefile). INFERRED that the active branch was the literal, assuming the posted build used this `makefile.inc`. |
| **Boot-time RAM fill** | `boot()` writes `0xdeadbeef` to every word in `[0, MEMISOSTART)` when `MEMISOSTART < 0x01000000`. Active with `0x00c80000` (P:1993–2002). | None | SOURCE VERIFIED. This is the instrument behind ranma's reported "wrote the whole RAM with 0xdeadbeef" method. It overwrote low RAM, TCM-adjacent areas and any non-Canon data below 12.5 MiB at every boot. |
| **Kernel copy sequence** (`fw_boot`) | Replicates `0xfc02000c`: stack `0x4000`, `sub_fc02007e`, `0xc0242010 \|= 1`, RAM-code copy, D-clean, TCM copy, **CreateTask patch install**, low-RAM copy, BSS zero → `sub_fc05b3c9_my` (P:1373–1437) | Same sequence **without** the CreateTask patch (C:85–157) | SOURCE VERIFIED |
| **Heap descriptor / kernel start** | `0x6ce000 − base ≥ 0xb1fec`, writes `0x8074/78/7c`, descriptor `{0x60e000, 0xc0000, base, 0x600014−base, 0x600014, 0x60e000, limits…}`, `blx sub_fc31b430` (P:1541–1598) | Identical structure and constants (C:179–252) | SOURCE VERIFIED. Bears on the PORT-4C pool-bound contradiction (F6). |
| **Init task** | `sub_fc05b559_my`: term/stdio/stdlib/extlib setup (P:1606–1675) | `sub_fc05b558_my`: same, with differing check words (C:264–332) | SOURCE VERIFIED; difference at F3 |
| **Startup spawner / power-on cause** | **Bypasses** `IsNormalCameraMode` (`sub_fc079404`) and `sub_fc1284ac`, which are commented out with the TODO "Find out why the default handler in sub_fc1284ac is broken" (P:1681, 1697–1703). Writes the start cause to `*(0x9bc4+0xc)` from button-register reads: power `0x80000`, Wi-Fi `0x40000`, otherwise Play `0x100000` (P:1685–1691). Then `CreateTask("Startup", 0x19, task_Startup_my)` (P:1713–1717). | **Calls** `sub_fc079404` and `sub_fc1284ac`. On zero → `sub_fc05ba56` then halt loop (C:342–350). Then the same CreateTask. | SOURCE VERIFIED. The "broken handler" is HISTORICALLY REPORTED (TODO comment). F2. |
| **StartDiskboot omission** | `bl sub_fc05bbea` commented out ("startdiskboot") (P:1736) | Omitted (C:374) | SOURCE VERIFIED; same decision |
| **`_DisableSDCard`** | Called in `task_Startup_my` (P:1739), comment "switch off card, trial (near SdPower.C SD1stInit)", referencing forum topic 13089 (UHS detection). Stub `NHSTUB(DisableSDCard, 0x10e172f)` in RAM-copied code (P:9074). | Not used | SOURCE VERIFIED that it is called. The effect is UNKNOWN ("trial"). |
| **SD1stInit** | Not created explicitly (StartDiskboot, which spawns it in our analysis, is omitted). Only `_DisableSDCard`. | RESTART-SD-1: replicates the stock gate `sub_fc05c4e0(0)` bit 0 and calls the SD1stInit creator veneer `sub_fc31b1f4` (C:386–398) | SOURCE VERIFIED difference. How ranma's camera initialised SD without SD1stInit is UNKNOWN. Not investigated further (SD write-site enumeration is classifier-closed). |
| **Task creation and hooks** | One generic hook: an 8-byte `ldr.w pc,[pc,#0]; .long CreateTask_my+1` written over `hook_CreateTask` (`0xbfe14a3c`) right after the TCM copy (P:1407–1411, 1433–1436). `CreateTask_my` swaps `r3` (entry) for four tasks, then replays the overwritten `stmdb sp!,{r1-r9,lr}; mov r4,r0; ldr r0,=0x8160` and jumps to `hook_CreateTask+8+1` (P:1453–1525). | No CreateTask patch. Only `task_Startup` is replaced (by spawning `task_Startup_my`). Stock `task_PhySw` runs unmodified. | SOURCE VERIFIED. F4. The replayed literal `0x8160` and the C validity of the `0x2de9fe43` (= `push {r1-r9,lr}`) prologue match are UNKNOWN for 1.10C beyond the PORT-0B value. |
| **SpyTask startup** | `CreateTask_spytask()` at the end of `task_Startup_my` after `sub_fc0bb6fe` (P:1759); `init_required_fw_features()` focus/ND event flags with "TODO: Check if needed on G3X" (P:1353–1369). SpyTask is gated by `core_spytask_can_start()` in the InitFileModules hook (P:1784). | SpyTask disabled ("Prevents premature thread execution and 10-second timeout unhooked crash", C:411–416) | SOURCE VERIFIED. F5 (INFERRED link). |
| **Continuation** | `b.w sub_fc0d0126` (P:1762) | `b.w sub_fc0d0126` (C:434) | SOURCE VERIFIED: the same address in both builds. Whether `fc0d0126` is the correct 1.10C continuation is supported only by our own docs ([PORT-2A safety gate](CHDK_PORT2A_SAFETY_GATE.md), [PORT-2B1](CHDK_PORT2B1_RESTART_PRECONDITIONS.md)). |
| **Soft-reboot flag** | `0x12345678 @ 0x4ffc` disabled ("Doesn't seem to work on this model") (P:2004–2008, 665–666) | Not used | HISTORICALLY REPORTED |
| **FI2 boot** | Supported: `KEYSYS=d4g`, `FI2FLAGS=W`, `NEED_ENCODED_DISKBOOT=13` (P:626–633). Empty `d4g` key block added upstream (P:113–116). TricInitTask workaround. | DISKBOOT only (encoding row 13, "dancingbits") | SOURCE VERIFIED. FI2 is out of scope. |

## 6. Boot-flow diagrams

Both flows begin at Canon's DISKBOOT entry. Steps marked `≠` differ.

```
ranma GM1.10E (source)                          our GM1.10C prototype
──────────────────────                          ─────────────────────
entry.S: sp=0x8000                              loader: witness, core copy
my_restart: check_compat                         → 0x003489B4
  core_copy → 0x00C80000  ≠                     D-clean+inv, dsb/isb
  D-clean (no IRQ mask)   ≠                     cpsid if               ≠
  bx 0x00C80001                                  bx 0x003489B5
        │                                               │
startup(): zero CHDK .bss                       (core entry)
boot(): fill [0,0xC80000) 0xDEADBEEF  ≠                 │
        │                                               │
fw_boot (= 0xfc02000c replica)                  boot (= 0xfc02000c replica)
  RAM-code copy, D-clean, TCM copy                RAM-code copy, D-clean, TCM copy
  ► patch hook_CreateTask (0xbfe14a3c)  ≠         (no CreateTask patch)
  low-RAM copy, BSS zero → 0x3489b4               low-RAM copy, BSS zero → 0x3489b4
        │                                               │
sub_fc05b3c9_my                                 sub_fc05b3c8_my
  heap base = 0x3489b4 (no shift)  ≠              heap base = new_sa (shifted)  ≠
  descriptor, blx kernel init                     descriptor, blx kernel init
        │                                               │
sub_fc05b559_my (init task)                     sub_fc05b558_my (init task)
  USER_MEM: [0x80ec] vs [0x8074]  ≠               USER_MEM: [0x80f0] vs [0x8078]
        │                                               │
sub_fc05b963_my                                 sub_fc05b962_my
  start cause from buttons (no fc1284ac)  ≠       stock fc079404 + fc1284ac  ≠
  CreateTask("Startup", task_Startup_my)          CreateTask("Startup", task_Startup_my)
        │                                               │
task_Startup_my                                 task_Startup_my
  StartDiskboot omitted                           StartDiskboot omitted
  _DisableSDCard  ≠                               SD1stInit gate + creator  ≠
  … stock init (PhySw created → hooked) ≠        … stock init (PhySw stock)
  CreateTask_spytask  ≠                           (spytask disabled)
  b.w sub_fc0d0126                                b.w sub_fc0d0126
        │                                               │
Canon continues; CreateTask_my swaps            Canon continues; no task swaps
PhySw / InitFileModules / FileWrite /
TricInitTask as Canon creates them
```

## 7. Memory map comparison

| Range | ranma GM1.10E | Ours GM1.10C | Status |
|---|---|---|---|
| `0x00000000–0x00003FFF` | ATCM, 16 KiB, exception vectors (notes P:688) | Vectors copied from `0xFC05B47C` (C:93) | E: HISTORICALLY REPORTED (notes) |
| `0x00008000–0x0003F4F3` | Canon low-RAM data (P:1413–1421) | Same range (C:133–142) | SOURCE VERIFIED (both texts) |
| `0x0003F4F4–0x003489B3` | Canon BSS (P:1422–1429) | Same (C:144–153) | SOURCE VERIFIED |
| `0x003489B4–0x006CDFFF` | Default Canon heap, **unshifted** (P:689–690, 1536) | `0x003489B4–0x00366C8F` CHDK core; heap from `0x00366C90`, upper `0x00600014` | SOURCE VERIFIED / VERIFIED (doc, manifest) |
| `0x0060E000` (+`0xC0000`) | Descriptor fields sp[0], sp[4], sp[0x14] (P:1562–1568) | Same fields (C:206–212) | SOURCE VERIFIED. F6. |
| `0x006CE000–0x006EFFFF` | Canon ARAM heap found by sigfinder (`0x22000`). **Commented out** in favour of the custom range (P:609–611). Notes give the end as `0x006fffff` (P:692). | Our `ARAM_HEAP_START`/`SIZE` with `OPT_ARAM_MALLOC=1` | SOURCE VERIFIED. ranma abandoned this region for CHDK; we use it for CHDK malloc. |
| `0x00700000–0x0075FFFF` | "OMAR ram area" (P:693–694) | Not documented | HISTORICALLY REPORTED |
| `0x00760000–0x007FFFFF`, `0x00B14DF0–0x00BFFFFF`, `0x00C16B90–0x00DFFFFF` | "Potentially unused" (P:705–708) | Not documented | HISTORICALLY REPORTED; never shown free |
| `0x00A00000–0x00B14DEF` | Zico Xtensa code (`zico_2` at uncached `0x80a00000`, P:799, 2599) | Zico blob copy to `0x80A00000` (E068, HANDOFF) | Consistent across builds |
| **`0x00C80000–0x00DFFFFF`** | **`ARAM_HEAP_START=0x00c80000`, `ARAM_HEAP_SIZE=0x00180000` (P:613–614): CHDK core plus CHDK ARAM malloc.** It ends exactly at `0x00E00000`, the "more Xtensa? (audio/video codec)" region (P:801) and the TricInit avcore RAM base (P:732, SX280 analogy). | Not used | SOURCE VERIFIED values. Free-ness is HISTORICALLY REPORTED ("seems", "needs more testing") and UNKNOWN on both builds. |
| `0x00E00000–` | Xtensa / avcore (notes) | Not documented | HISTORICALLY REPORTED |
| `0x010E1000–0x01107CFF` | RAM-copied code (includes `DisableSDCard` at `0x010E172F`) | Same copy range | SOURCE VERIFIED (both texts) |
| `0xBFE10800–0xBFE17418` | TCM kernel copy; notes call `0xbfe10000` the **BTCM** (P:700) | Copy labelled "ATCM" (C:122) | Naming conflict only. ranma's label matches the ATCM-at-0 note. |
| `0x20000000`/`0x40000000` | RAM mirror / uncached mirror (P:699, 711) | Consistent with PORT-5A post 143435 | HISTORICALLY REPORTED |

Note on `makefile.inc`: the comment "Force ARAM on, but **don't** load CHDK in ARAM, because size is marginal for core" (P:616) contradicts the next line, `OPT_CHDK_IN_ARAM=1` (P:618). The comment is stale from the G5X fork; the value governs. The 1.5 MiB size is sized for the core plus malloc, where the original 136 KiB was "marginal".

## 8. Historical task-hook analysis

All four hooks are installed by the single CreateTask patch (§5). They swap the entry pointer only, except PhySw, which also enlarges the stack.

| Hook | Stock entry (E) | Replacement | What it does | Status |
|---|---|---|---|---|
| **PhySw** | `task_PhySw 0xfc1283ad` (P:9042) | `mykbd_task`, stack `0x800 → 0x2000` (P:1460–1465) | Loop: `SleepTask(physw_sleep_delay)`, `wrap_kbd_p1_f` → `my_kbd_read_keys`, then `kbd_p2_f_my`, a copy of `fc12811e` whose tail calls `sub_fc08ede0_my`, which adds `handle_jogdial` and can suppress Canon's scroll handling (P:184–199, 1798–1930). Keymap with 19 keys and levent annotations (P:148–169). | SOURCE VERIFIED. Jog-dial "working and mostly tested": HISTORICALLY REPORTED (P:661). |
| **InitFileModules** | `0xfc0bd071` (P:9040) | `init_file_modules_task`, a copy of the 17-instruction stock task (P:1769–1795) | Inserts `core_spytask_can_start()` after `sub_fc0d9cf6`, i.e. after file modules are up, before the final UI event. In r5480 `core/main.c:101–103` that function sets `spytask_can_start = 1`. | SOURCE VERIFIED (patch + upstream) |
| **FileWrite** | `0xfc25f3cf` (P:9039) | `filewritetask` (P:2073…) plus `fwt_data_struct` | PTP remote-capture file interception. "Based on G16 filewrite.c … struct offsets appear to match" (P:2021) and "Copied from G5X port" (P:2038), with a 110E memory dump as evidence (P:2040–2056). | SOURCE VERIFIED structure. Correctness is HISTORICALLY REPORTED and partly negative: "Remote shooting stops working after the first photo" (P:652–653). |
| **TricInitTask** | `0xfc4e4b41` (P:9044) | `task_TricInitTask_my`, a stock copy (P:1932–1985) | Adds: if the avcore control word `TRIC_CTL` (`0xd2020074`) reads non-zero (core already running after an FI2 boot), set event flag `0x80` on the Tric flag object, then continue in firmware at `0xfc4e4b9d`. Comment: "Only needed for FI2 boot" (P:1482). Background: srsa_4c analysis quoted in notes (P:727–738). | SOURCE VERIFIED code. Necessity and effect are HISTORICALLY REPORTED. Contains an MMIO read; not investigated further and not applicable to DISKBOOT scope. |

Hooks present but **commented out**: CaptSeq, ExpDrv, DvlpSeq, MovieRecord and TskCocoa0 (P:1485–1513). `hook_raw_save_complete` is a TODO stub (P:1328–1330). **SOURCE VERIFIED:** no capture, exposure or movie integration existed. This matches ranma's "~minimum of task hooks".

## 9. Ranked findings

| # | Finding | Evidence | Status |
|---|---|---|---|
| **F1** | **Different core residency model.** ranma ran CHDK at `0x00C80000` outside Canon's heap with **no heap shift**. Ours places the core at the bottom of Canon's heap (`0x3489B4`) and shifts the heap base. ranma reported that moving CHDK out of the Canon heap cured live-view crashes ("seems", PORT-5A post 143436). | P:613–624, P:1535–1540; upstream r5480 `makefile.inc:214–215`; candidate manifest | Placement SOURCE VERIFIED. The stability benefit is HISTORICALLY REPORTED. The safety of `0x00C80000` is UNKNOWN on both builds. |
| **F2** | **Power-on handler bypass.** ranma replaced the stock `IsNormalCameraMode` + `sub_fc1284ac` check with a hand-built start cause, citing a broken default handler in the restart context. Our prototype still calls the stock path, whose failure branch powers down (`sub_fc05ba56`) and halts. | P:1681–1703 vs C:342–350 | SOURCE VERIFIED difference. "Broken" is HISTORICALLY REPORTED (E only). Whether 1.10C behaves the same is UNKNOWN, and it is a plausible early-boot failure mode for our design. |
| **F3** | **Transcription discrepancy in our init-task replica (RESOLVED).** E checks `[0x80ec] ≥ [0x8074]+0x10`. Our C replica originally checked `[0x80f0] ≥ [0x8078]+0x10`. Both builds write `0x8074 = 0x80000` and `0x8078 = 0x42281000` in the preceding stage (P:1550–1558; C:190–198; [PORT-1B heap proof](CHDK_PORT1B_HEAP_PROOF.md) for C). **Resolved by PORT-5D / PORT-5E (ROM VERIFIED):** GM1.10C ROM inspection confirms `[0x80EC]` vs `[0x8074]+0x10`; the prototype's constants and all 8 string references were a systematic +4 transcription error, now corrected in PORT-5E. | P:1614–1618 vs C:270–274; PORT-5D §2 | Difference SOURCE VERIFIED; 1.10C ROM VERIFIED by PORT-5D; corrected in PORT-5E. |
| **F4** | **Task integration method.** ranma used one 8-byte inline patch of the TCM-resident `CreateTask` (`hook_CreateTask 0xbfe14a3c`, the same TCM address recorded for C) to redirect four tasks. Ours has no task interception. The historical design shows that CHDK's standard hook point exists at the same TCM address in E. It does **not** validate the replayed prologue/literal (`0x8160`) for C. | P:1407–1436, 1453–1525; PORT-0B stubs audit | SOURCE VERIFIED (E). For C, UNKNOWN beyond the PORT-0B value. Task/CreateTask investigation remains outside current scope (PORT-4D boundary). |
| **F5** | **SpyTask gating explains a standard dependency.** ranma starts SpyTask in task_Startup, and it waits for `spytask_can_start`, which only the InitFileModules hook sets. Our prototype removed SpyTask because of a "10-second timeout unhooked crash". INFERRED: that symptom is consistent with SpyTask running without the InitFileModules gate it depends on, which is how upstream CHDK sequences it. | P:1759, 1784; r5480 `core/main.c:31, 101–103`; C:411–416 | INFERRED; not tested |
| **F6** | **PORT-4C pool-bound "contradiction" is two fields.** Both texts place `0x0060E000` (with `0xC0000`) and `0x00600014` in different descriptor slots: sp[0]/sp[0x14] vs sp[0x10], with heap size = `0x00600014 − base`. That reads as two distinct parameters, not conflicting values for one bound. | P:1562–1568; C:206–212 | INFERRED (both texts agree; descriptor semantics not proven). The PORT-4C contradiction should be reworded rather than counted as resolved. |
| **F7** | **SD handling diverges.** ranma powers the card off (`_DisableSDCard`, labelled "trial") and does not spawn SD1stInit. Ours re-creates SD1stInit via the stock gate. Neither documents the post-restart SD state. | P:1736–1739, 9074 vs C:386–398 | SOURCE VERIFIED difference; effect UNKNOWN. The PORT-3 SD blocker is unchanged. |
| **F8** | **No IRQ masking in the historical loader.** ranma's restart ran without `cpsid`, I-cache invalidation or interrupt-controller handling, and is reported to reach Playback. | P:47–101 | SOURCE VERIFIED absence. The boot outcome is HISTORICALLY REPORTED. It is **not** evidence that the PORT-3 IRQ risk is benign: one unstable experimental build on 1.10E. |
| **F9** | **E→C address relation is irregular.** Some offsets are 0, some −0x28, some +4, even within one boot path (§4). | §4 | Observation SOURCE VERIFIED. Cause UNKNOWN. |
| **F10** | **Base revision proven.** r5480, against our r5491. | §3 | SOURCE VERIFIED |

## 10. Effect on previous boot assumptions

- **Confirmed (two independent authors, same structure):**
  - The `0xfc02000c` replica.
  - The heap-descriptor stage.
  - StartDiskboot omission.
  - Continuation at `fc0d0126`.
  - Spawning a replacement `task_Startup`.

  Our prototype is in the mainstream CHDK pattern. It was evidently derived in parallel from the same G5X lineage (P:648; C:8).
- **Challenged:**
  - The choice to keep the stock power-on check (F2).
  - The unverified stage-4 check words (F3).
  - The assumption that placing the core inside the Canon heap is the natural layout (F1). ranma moved away from it after instability.
- **Unchanged:**
  - Warm-restart IRQ/SD/continuation blockers (PORT-3C, PORT-4B).
  - C residency and G6 (PORT-4C/4D).
  - Hardware NO-GO.

Nothing in the patch is hardware evidence for 1.10C.

## 11. Conceptually adaptable to GM1.10C (ideas only; nothing implemented)

1. The **InitFileModules gate** for any future resident task: start only after file modules signal readiness.
2. The **single CreateTask interception point** as the reference design for Architecture A/C task integration. It would need its own scoped approval, because task investigation is currently excluded.
3. Treating **power-on cause determination** as an explicit design item rather than inheriting the stock handler.
4. **Core outside the Canon heap** as an alternative to heap shifting. It requires a proven-free region, which no evidence currently provides.
5. The **minimum-hook inventory** (PhySw, InitFileModules, FileWrite; TricInitTask only for FI2) as a scope checklist.

Not adaptable as-is: any 1.10E address, the `0xdeadbeef` boot fill, the TricInit MMIO workaround, and `_DisableSDCard` (a "trial", with its effect unknown).

## 12. Outstanding blockers

1. **PORT-3C/PORT-4B restart blockers** (IRQ pending state, SD recovery, continuation) are not resolved by historical source. The classifier-closed IRQ caller and SD write-site enumerations stay closed.
2. **C residency / G6** (PORT-4C/4D): unchanged.
3. **F3 check-word discrepancy (RESOLVED in PORT-5D / PORT-5E)**: ROM verified (`[0x80EC]` vs `[0x8074]+0x10`); isolated prototype literals corrected in PORT-5E.
4. **F2 power-on path**: 1.10C behavior is UNKNOWN.
5. **Free-memory proof** for any non-heap core region (`0x00C80000–0x00DFFFFF` or other) on 1.10C: none exists.
6. **Hardware**: STRICT NO-GO. No phase transition is implied.

## 13. Recommended next research milestone

**PORT-5C — Prototype-vs-ROM reconciliation of F3 and F2 (documentation-first).**
1. Search existing project evidence for GM1.10C stage-4 data: PORT-1A/1B/1C traces, `funcs_by_address` outputs, and the stubs audit.
2. Look for the instructions at `0xFC05B558–0xFC05B574` and the power-on path at `0xFC05B962–0xFC05B978`.
3. If the evidence is absent, request **owner approval** for a bounded read of exactly those two ROM ranges. This is not a teardown, IRQ, SD or task investigation.
4. Output: a correction note for `boot_prototype.c`, with no code change until reviewed.

In parallel, as documentation only: reword the PORT-4C pool-bound contradiction per F6. Separately, move the patch into a labelled historical-reference directory such as `historical/ranma_g3x_110e/`, with a README holding its hash and provenance. That move is a file relocation for the owner to approve. It is not part of this read-only task.

## 14. Boundary record

- **Done:**
  - Hash and size verification.
  - Text reading of the patch.
  - Comparison with our prototype source and documents.
  - Read-only fetch of upstream r5479/r5480/r5491 text files from `01luna/CHDK` for preimage matching.
- **Not done:**
  - `git apply` (including `--check`), patch builds, ROM disassembly or binary reads.
  - Modification of any executable, firmware, loader or test file.
  - Retrying classifier-closed work.
  - Camera, SD or hardware actions; commits, pushes or PRs.
  - The patch file was left in place and unmodified.

Exact next command:

```sh
cat /Users/avp/project/g3x-lite/docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md
```
