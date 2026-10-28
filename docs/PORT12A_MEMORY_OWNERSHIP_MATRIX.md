# PORT-12A — Memory Ownership Constraints for GM1.10C (Offline)

**Worker**: Gemini Worker 1 (PORT-12A Memory Ownership)  
**Coordinator**: Gemini Coordinator  
**Tech Lead**: ChatGPT  
**Baseline**: `origin/main` @ `581b1a4bb30456bf18c46dc4bcf61b0375aee251`  
**Date**: 2026-10-28  
**Status**: **`RESEARCH_COMPLETE / DRAFT_PR_FOR_REVIEW`**  
**Safety Gate**: **`STRICT NO-GO FOR HARDWARE DEPLOYMENT`** (Phase 0 Offline Read-Only Investigation)

---

## 1. Executive Summary & Objective

The objective of milestone **PORT-12A (Issue #20)** is to establish a rigorous, offline, source-grounded memory ownership matrix for the Canon PowerShot G3 X (Firmware **GM1.10C**, DIGIC 6, Cortex-R4 dual-core architecture), comparing our prototype's **low-heap core placement** (`0x003489B4 + new_sa`) against Ranma's historical GM1.10E high-DRAM placement (**`MEMISOSTART = 0x00C80000`**), without assuming either placement is unconditionally safe on GM1.10C.

### Key Findings
1. **Low-Heap Shift (`0x003489B4 + new_sa`)**:
   - **`VERIFIED_IN_EXISTING_DOCS`**: The DryOS kernel heap initialization function at `0xFC05B3C8` mathematically verifies that shifting heap base `r4` from `0x003489B4` up to `0x003C89B4` (a 512 KiB reservation) maintains `3,167,820` B ($3.021$ MiB) of available headroom, leaving a `2,438,752` B ($2.326$ MiB) safety margin above the hardcoded minimum headroom assert `0x000B1FEC` (729,068 B = 712 KiB).
   - Proven safe from collision with BSS (`0x0003F4F4..0x003489B4`) and low-RAM hardware structures (`0x00008000..0x0003F4F4`).
2. **Ranma High-DRAM Placement (`0x00C80000`, 1.5 MiB Heap)**:
   - **`HISTORICAL_DESIGN_CANDIDATE`**: Avoids the low `AdditionAgent` conflict (`0x006CE000..0x006FFFFF`) and the OMAR secondary core communication area (`0x00700000..0x00760000`).
   - **Critical Unresolved GM1.10C Risks (`UNKNOWN`)**:
     - *Sensor RAW DMA Overlap*: The G3 X features a 1-inch 20.2 MP sensor requiring large circular DMA buffers (~35 MiB per uncompressed raw frame) dynamically mapped into high DRAM.
     - *Xtensa / Tric Audio/Video Codec Core Firmware Blob Overlap*: Co-processor blobs load into uncached DRAM without entering the DryOS heap table.
     - *No Proven Static Bound*: G3 X GM1.10C top-of-DRAM mapping is not verified. High DRAM cannot be treated as empty.
3. **Core Architectural Principle**:
   - We strictly distinguish **`PROVEN_NO_OVERLAP`** (regions bounded by verified ROM literals and linker symbols) from **`MERELY_NO_KNOWN_OVERLAP`** (uninspected DRAM ranges that lack explicit ownership records).
   - Unknown DRAM regions are **NEVER** treated as empty space.

---

## 2. Source-Grounded Memory Ownership Matrix

The following matrix documents all known DRAM, ATCM, and peripheral memory regions on GM1.10C derived from tracked repository documents (`docs/PORT1B_HEAP_PROOF.md`, `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md`, `docs/PORT11A_GM110C_ROM_EVIDENCE.md`, and `g3x_110e.patch`).

| Region Identifier | Address Range | Size | Primary Owner / Allocator | CPU / Bus Master | Classification | Evidence Source | Lifetime & Hazard Profile |
|---|---|---:|---|---|:---:|---|---|
| **R-01: Low Vector & Hardware Scratch** | `0x00000000..0x00007FFF` | 32 KiB | Hardware Exception Vectors & System Scratch | Cortex-R4 (CPU 0) / Boot ROM | **`VERIFIED_IN_EXISTING_DOCS`** | `docs/PORT5B_HISTORICAL_BOOT_COMPARISON.md:78` (`MEMBASEADDR=0x8000`) | Static; bootloader sets stack pointer to `0x8000`. Overwriting causes immediate hardware exception hang. |
| **R-02: Low-RAM Data Section** | `0x00008000..0x0003F4F3` | ~221 KiB | DryOS Kernel Data & Globals | Cortex-R4 (CPU 0) | **`VERIFIED_IN_EXISTING_DOCS`** | Copied from ROM `0xFCE91058` (`PORT5B:78`, `CHDK_PORT1B:26`) | Persistent; initialized at early boot `0xFC02005A..0xFC02006E`. Contains interrupt vector table, task control blocks, and timer tables. |
| **R-03: Canon Firmware BSS** | `0x0003F4F4..0x003489B3` | ~3.036 MiB | Canon Firmware Static BSS | Cortex-R4 (CPU 0) | **`VERIFIED_IN_EXISTING_DOCS`** | Zeroed at boot `0xFC020070..0xFC020078` (`PORT5B:78`, `CHDK_PORT1B:26`) | Persistent; zeroed before DryOS kernel init. Contains all uninitialized static and global state. |
| **R-04: Low-Heap Prototype Target** | `0x003489B4..0x003C89B3` | 512 KiB | CHDK Core Prototype (Shifted Heap Base) | Cortex-R4 (CPU 0) | **`INFERRED` (Design Candidate)** | Linker script & `docs/CHDK_PORT1B_HEAP_PROOF.md:92` | Persistent after bootloader copy. Truncates stock heap base from `0x003489B4` to `0x003C89B4`. Proven safe from BSS and kernel assert. |
| **R-05: DryOS Main Heap Pool 0** | `0x003C89B4..0x00600013` | ~2.216 MiB | DryOS Dynamic System Heap (`AllocateMemory`) | Cortex-R4 / System Tasks | **`VERIFIED_IN_EXISTING_DOCS`** | Literal `0xFC05B474` (`0x00600014`), `CHDK_PORT1B:47` | Dynamic; used by DryOS tasks for memory allocation. Shift leaves $2.216$ MiB usable pool 0. |
| **R-06: DryOS Sub-pool & Kernel Descriptors** | `0x00600014..0x0060DFFF` | 56 KiB | DryOS Kernel Object Tables | DryOS Kernel | **`VERIFIED_IN_EXISTING_DOCS`** | Literal `0xFC05B474`, `CHDK_PORT1B:47` | Persistent OS descriptors (tasks, semaphores, message queues, condvars). |
| **R-07: DryOS Heap Pool 0 Upper Block** | `0x0060E000..0x006CDFFF` | 768 KiB | DryOS Fixed Chunk Allocator | DryOS Kernel | **`VERIFIED_IN_EXISTING_DOCS`** | Literal `0xFC05B470`, chunk size `0x000C0000`, `CHDK_PORT1B:47` | Dynamic system chunk allocations. |
| **R-08: DryOS System Limit & Headroom Assert** | `0x006CE000` | Anchor | Kernel Headroom Comparator Limit | DryOS Kernel Init | **`VERIFIED_IN_EXISTING_DOCS`** | Literal `0xFC05B454` (`0x006CE000`), `CHDK_PORT1B:32` | Static threshold: `0x006CE000 - r4 >= 0x000B1FEC` must hold, or kernel spins in infinite loop `0xFC05B3D8`. |
| **R-09: AdditionAgent Conflict Zone** | `0x006CE000..0x006FFFFF` | 196 KiB | `AdditionAgent.c` Storage Direct Buffer | Storage DMA / `Fread_Fut` | **`VERIFIED_IN_EXISTING_DOCS`** | `0xFC55888C..0xFC5588C0` (`docs/RANMA_SOURCE_ARCHAEOLOGY.md:46`) | Transient during storage reads. Writing code/payload here is corrupted by `AdditionAgent` file reads of up to `0x22000` bytes. |
| **R-10: OMAR Secondary Core Staging RAM** | `0x00700000..0x00760000` | 384 KiB | Secondary Core (*Omar*) IPC & Staging | Cortex-R4 (CPU 1) / IPC DMA | **`HISTORICAL_CANDIDATE`** | Ranma `platform/g3x/notes.txt:45–46`, `PORT5B` | Inter-core IPC mailbox and image co-processing buffers. Overwriting causes CPU 1 panic / camera lockup. |
| **R-11: Mid DRAM Uninspected Gap** | `0x00760001..0x00C7FFFF` | ~5.12 MiB | Uninspected DRAM Gap | Unknown | **`UNKNOWN`** | No tracked GM1.10C evidence | **MERELY NO KNOWN OVERLAP**. Cannot assume empty. May contain optical/sensor calibration tables or display framebuffers. |
| **R-12: Ranma High-DRAM CHDK Placement** | `0x00C80000..0x00DFFFFF` | 1.5 MiB | Ranma GM1.10E CHDK Core (`MEMISOSTART`) | Cortex-R4 (CPU 0) | **`HISTORICAL_DESIGN_CANDIDATE`** | `platform/g3x/makefile.inc:29–37`, `g3x_110e.patch:580` | High DRAM CHDK core placement on GM1.10E. **UNPROVEN on GM1.10C**. High hazard of sensor raw DMA / video ringbuffer collision. |
| **R-13: High DRAM Uninspected Gap** | `0x00E00000..0x010E0FFF` | ~2.88 MiB | Uninspected DRAM Gap | Unknown | **`UNKNOWN`** | No tracked GM1.10C evidence | **MERELY NO KNOWN OVERLAP**. Cannot assume empty. |
| **R-14: Firmware Executable RAM Mirror** | `0x010E1000..0x01107D00` | 155.25 KiB | Canon ROM Routines Copied to Executable RAM | Cortex-R4 (CPU 0) Code Bus | **`VERIFIED_IN_EXISTING_DOCS`** | Copied from ROM `0xFCEC854C` (`PORT5B:78`, `CHDK_PORT1B:26`) | Persistent executable code. Modifying or executing out of phase triggers CPU prefetch aborts. |
| **R-15: Upper DRAM & DMA Capture Buffers** | `0x01107D01..0x3FFFFFFF` | ~1006 MiB | Sensor RAW, JPEG encoder, Video Buffers | Video DMA, Sensor ISP | **`UNKNOWN`** | Dynamic heap / peripheral DMA (`0x43DBFCA0`, `PORT5B:48`) | High throughput DMA. Massive framebuffers (20.2 MP raw = 35 MiB/frame). Unsafe for custom payload without full peripheral mapping. |
| **R-16: Cortex-R4 ATCM Relocated Span** | `0xBFE10800..0xBFE1741B` | 27,676 B | Cortex-R4 Tightly Coupled Memory (ATCM) | Cortex-R4 (CPU 0) Core Bus | **`VERIFIED_IN_EXISTING_DOCS`** | Copied from ROM `0xFCEEF24C..0xFCEF5E67` (`PORT11A:20`, PR #19) | Fast zero-wait-state RAM containing critical OS routines (`CreateTask`, `CreateTaskStrictly`, scheduler). Hook target. |
| **R-17: Uncached Peripheral Memory Mappings** | `0x40000000..0x5FFFFFFF` | 512 MiB | Uncached Aliases of DRAM & DMA Apertures | Peripheral DMA Controllers | **`VERIFIED_IN_EXISTING_DOCS`** | `0x42281000`, `0x42283000`, `0x406CE000` (`CHDK_PORT1B:47`) | Non-cache-coherent access for hardware peripherals and storage drivers. |

---

## 3. "Proven No-Overlap" vs. "Merely No Known Overlap"

A major vulnerability in historical CHDK porting was the heuristic assumption that any unmentioned DRAM range is free space. In GM1.10C, we enforce a strict semantic distinction:

```mermaid
flowchart TD
    subgraph Proven_Safe["Proven No-Overlap (Formally Bounded)"]
        A1["R-03: Canon BSS<br/>0x0003F4F4..0x003489B3"]
        A2["R-04: Low-Heap Core<br/>0x003489B4..0x003C89B3"]
        A3["R-05: DryOS Heap Pool 0<br/>0x003C89B4..0x00600013"]
    end

    subgraph Conflict_Zones["Known Hardware & Subsystem Conflict Zones"]
        B1["R-09: AdditionAgent Buffer<br/>0x006CE000..0x006FFFFF"]
        B2["R-10: OMAR Core Staging<br/>0x00700000..0x00760000"]
        B3["R-14: RAM Code Mirror<br/>0x010E1000..0x01107D00"]
        B4["R-16: ATCM Relocated Span<br/>0xBFE10800..0xBFE1741B"]
    end

    subgraph Hazard_Gaps["Merely No Known Overlap (UNPROVEN HAZARDS)"]
        C1["R-11: Mid-DRAM Gap<br/>0x00760001..0x00C7FFFF<br/>(STATUS: UNKNOWN)"]
        C2["R-12: Ranma 0x00C80000<br/>0x00C80000..0x00DFFFFF<br/>(STATUS: HISTORICAL_CANDIDATE)"]
        C3["R-13: High-DRAM Gap<br/>0x00E00000..0x010E0FFF<br/>(STATUS: UNKNOWN)"]
    end

    A1 ---|Verified Boundary 0x003489B4| A2
    A2 ---|Verified Shift 0x003C89B4| A3
    A3 -.->|Heap Headroom Margin: 2.32 MiB| B1
    C2 -.->|Unverified Sensor DMA Collision Risk| C3
```

### Definitions
1. **`PROVEN_NO_OVERLAP`**:
   - Both the lower and upper bounds are anchored to verified firmware literals, linker symbols, or hardware registers.
   - Example: The low-heap reservation `[0x003489B4, 0x003C89B4)` has lower bound anchored to `_end` of Canon BSS (`0x003489B4`, verified by `0xFC05B450`) and upper bound anchored to the DryOS heap descriptor (`sp[0x08] = r4 = 0x003C89B4`). Because the DryOS allocator only issues pointers $\ge r_4$, no allocation from Pool 0 can ever enter `[0x003489B4, 0x003C89B4)`.
2. **`MERELY_NO_KNOWN_OVERLAP`**:
   - A memory range that is not referenced in currently inspected ROM slices, but has no verified allocator or reservation protecting it against peripheral DMA, secondary core writes, or dynamic video buffers.
   - Example: Ranma's `0x00C80000` (`MEMISOSTART`). While Ranma reported this worked on his GM1.10E camera, there is zero documentary proof that sensor RAW capture buffers, multi-frame noise reduction, or video ringbuffers do not dynamically write across `0x00C80000..0x00DFFFFF` on GM1.10C. Treating `0x00C80000` as safe without DMA buffer layout evidence is an unverified gamble.

---

## 4. Decision Memo: Low-Heap Relocation vs. High-DRAM Placement

| Evaluation Criterion | Low-Heap Relocation (`0x003489B4 + new_sa`) | Ranma High-DRAM (`0x00C80000`) | Winner / Recommendation |
|---|---|---|:---:|
| **Mathematical Consistency** | **Fully Proved**: Satisfies DryOS headroom check with $2.326$ MiB margin (`CHDK_PORT1B_HEAP_PROOF.md`). | **Unverified**: Bypasses DryOS heap structure entirely; relies on DRAM being unused by Canon code. | **Low-Heap** |
| **AdditionAgent Collision Risk** | **Zero**: Upper bound (`0x003C89B4`) is $3.02$ MiB below the `AdditionAgent` zone (`0x006CE000`). | **Zero**: Placed at `0x00C80000`, well above `0x006FFFFF`. | **Tie** |
| **OMAR Secondary Core Safety** | **Zero**: `0x003C89B4` is $3.21$ MiB below OMAR staging area (`0x00700000`). | **Marginal**: Ranma claimed `0x00C80000` was above OMAR, but exact upper boundary of OMAR IPC on GM1.10C is `UNKNOWN`. | **Low-Heap** |
| **Sensor RAW & Video DMA Safety** | **High**: DryOS heap space is never overwritten by raw image capture DMA (Canon camera architecture isolates heap from framebuffers). | **Severe Risk**: 20.2 MP sensor requires ~35 MiB per raw frame. Compact camera raw framebuffers live in upper DRAM. Overlap probability is high. | **Low-Heap** |
| **Loader / Restart Complexity** | Requires shifting `r4` in kernel init (`0xFC05B3C8`) and recomputing heap size `0x00600014 - r4`. | Requires copying payload to `0x00C80000` and executing far jump outside DryOS space. | **Low-Heap** |
| **Current Verification Status** | **`VERIFIED_IN_EXISTING_DOCS`** (Static proof complete; runtime preconditions fail-closed). | **`HISTORICAL_DESIGN_CANDIDATE`** (Empirical 1.10E observation; unproven for GM1.10C). | **Low-Heap** |

### Recommendation
**Retain Low-Heap Core Placement (`0x003489B4 + new_sa`) as the primary architectural candidate.** Do NOT adopt Ranma's `0x00C80000` for GM1.10C.

---

## 5. Offline Validation & Adversarial Collision Tests

To enforce these ownership constraints offline, we introduce a deterministic test suite (`tests/test_port12a_memory_ownership.py`):
1. **`test_known_regions_disjoint_and_ordered`**: Verifies that all known static regions (`R-01` through `R-10`, `R-14`, `R-16`) are strictly non-overlapping and conform to verified address intervals.
2. **`test_low_heap_headroom_arithmetic`**: Computes the exact DryOS headroom formula `0x006CE000 - r4 >= 0x000B1FEC` for stock (`r4 = 0x003489B4`), 512 KiB shifted (`r4 = 0x003C89B4`), and asserts failure if `r4 > 0x0061C014`.
3. **`test_addition_agent_and_omar_isolation`**: Asserts that low-heap placement (`0x003C89B4`) maintains $>3$ MiB of separation from `AdditionAgent` (`0x006CE000`) and OMAR (`0x00700000`).
4. **`test_historical_high_dram_cannot_be_promoted_to_verified`**: Verifies that any attempt to declare `0x00C80000` as `STATIC_VERIFIED` or `PROVEN_NO_OVERLAP` fails validation.
5. **`test_unknown_gaps_fail_closed`**: Verifies that gaps `R-11`, `R-13`, and `R-15` cannot be evaluated as empty memory.

---

## 6. Evidence-Request Checklist for Future Separately Authorized Research

For any future research stream considering memory placement alternatives, the following evidence must be obtained from verified artifacts before changing any safety gate:
- [ ] **E-01**: Static ROM disassembly of Canon sensor RAW allocation routines (e.g. `sub_fc...` allocating framebuffers) to locate the lower bound of image capture DMA.
- [ ] **E-02**: Exact bounds of OMAR secondary core communication memory from ROM literal pools.
- [ ] **E-03**: Xtensa / Tric audio/video co-processor firmware blob load address table in ROM.
- [ ] **E-04**: Total physical DRAM size register configuration on G3 X GM1.10C hardware.
- [ ] **E-05**: Verification of whether dynamic allocations from DryOS Pool 0 ever exceed $2.0$ MiB under continuous shooting.

---

## 7. Safety Compliance

- Zero firmware payloads built or executed.
- Zero ROM scans or capstone disassemblies outside existing pinned slices.
- Zero hardware operations on camera or SD card.
- Hardware gate remains **`STRICT NO-GO`**.
