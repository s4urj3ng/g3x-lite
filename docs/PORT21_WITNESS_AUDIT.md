# PORT-21 Witness Audit: Writer vs Inspector Roundtrip Verification (Hypothesis H4)

Labels: `[VERIFIED]` = shown by tracked source, a tracked artifact, or a host test in this repository; `[INFERRED]` = reasoning from verified facts, not directly observed; `[UNKNOWN]` = no evidence in the repository either way. No ROM reads, camera operations or card writes were done for this audit.

## 1. Executive Summary & Evaluation of Hypothesis H4

### 1.1 Objective & Context
During the physical camera execution trial for CHDK-PORT-2A (PowerShot G3 X GM1.10C), observation **O6** was recorded: the Canon Basic Witness Inspector reported `WITNESS_INVALID` on Line 1 (`h_title`) and `INVALID / CORRUPT` on Line 2 (`h_status`), returning sentinel `0x574954EE` (`docs/PORT18_OWNER_TRIAL_PLAN.md:267, 288`).

Hypothesis **H4** posits:
> *"The LOADER witness record at 0x0035F7A0 was malformed, given the code exactly as built."*

This audit compares the witness writer routines in the loader (`chdk-port/loader/g3x/main_prototype.c:42-56`) and core (`chdk-port/platform/g3x/sub/110c/boot_prototype.c:26-56`) field by field against the witness inspector parser (`firmware/tools/witness_inspector_payload.S`, loaded by `firmware/tools/witness_inspector_gm110c.m`, with host reference `tools/validate_witness_inspector.py`). **Which inspector payload the owner actually ran, and therefore which address it read, is `[UNKNOWN]`** (Section 2.3). Two 444-byte payloads exist: one reads `0x0035F780` and the other reads `0x0035F7A0`.

### 1.2 Epistemic Scope and Status of Hypothesis H4
- **Loader Code as Built Produces a Valid Record (`[VERIFIED]`)**:
  A host C probe compiling the real boot witness header (`chdk-port/platform/g3x/sub/110c/boot_witness.h`) and replicating field-by-field the loader's assignments (`main_prototype.c:42-56`) generates a 32-byte record with `magic=0x5749544E`, `version=0x00010001`, `session_nonce=0x32A80001`, `stage_state=0x01`, `loader_sp=0x00007FF8`, `core_entry_pc=0`, `cont_tick=0`, and `checksum=0x3028882D`.
  When parsed by the real inspector parse code (`vwi.emulate_inspector_parse`), this exact loader-only record produces:
  - Title: `LOADER_REACHED`
  - Status: `FRESHNESS_UNVERIFIED`
  - Color indices: Title Color 1 (White), Status Color 4 (Yellow)
  - Return Sentinel: `0x57495401` (`SENTINEL_LOADER`)
  - **A loader-only record is reported as valid (`[VERIFIED]`)** when it is read at the address it was written to (`0x0035F7A0`).
- **Writer/Parser Compatibility (`[VERIFIED]`)**:
  Struct layout, member offsets, 32-byte size, little-endian byte ordering, and checksum algorithm and coverage match between the loader writer and the inspector parser. No writer/parser mismatch was found in the record format.
- **Inspector Address Provenance (`[UNKNOWN]`, candidate explanation)**:
  The tracked payload `firmware/tools/witness_inspector_payload.bin` reads `0x0035F780`. Only the regenerated payload `candidate_port2a/witness_inspector_payload.bin` reads `0x0035F7A0` (Section 2.3, `[VERIFIED]`). If the owner ran the tracked payload, O6 describes memory at `0x0035F780`, not the LOADER record, and O6 says nothing about H2, H3 or H4 (`[INFERRED]`). T4 must rule this out.
- **Actual Hardware State during Trial O6 (`[UNKNOWN]`)**:
  - The RAM contents at `0x0035F780` and `0x0035F7A0` when the inspector ran during O6 are `[UNKNOWN]` (no raw memory dump was captured).
  - Whether the loader witness writer ever executed on the camera during the trial is `[UNKNOWN]`.
- **O6 Does Not Single Out One Hypothesis (`[INFERRED]`)**:
  The parser returns the same `WITNESS_INVALID / INVALID / CORRUPT` (`0x574954EE`) output for any 32-byte window that fails one of six predicates (Section 5.1). Many tested byte patterns hit those predicates (Section 5.2, `[VERIFIED]` by test). Several physical causes could produce them (Section 5.3, `[INFERRED]`, not exhaustive). So O6 alone does not discriminate between H1 to H4, or the inspector-address explanation.

---

## 2. Artifact Identification & Code Flow

### 2.1 The Witness Writers
1. **Loader Writer**:
   - Source: `chdk-port/loader/g3x/main_prototype.c:42-56` `[VERIFIED]`.
   - Invocation: `my_restart()` in `candidate_loader.elf`, executed immediately after `core_copy()` (`main_prototype.c:38`) and prior to cache synchronization and the branch to `0x003489B5` `[VERIFIED]`.
   - Target Address: `BOOT_WITNESS_ADDR` (`0x0035F7A0`), passed via `-DBOOT_WITNESS_ADDR=0x0035f7a0` in `tools/build_candidate_port2a.py:506`; the literal `0x0035F7A0` is present at loader offset `0x254` (asserted in `test_disassembly_coherence_and_sp_provenance`) `[VERIFIED]`.
   - Stack Pointer Provenance:
     - `chdk-port/loader/g3x/entry.S:7`: `LDR SP, =MEMBASEADDR` initializes SP to `0x00008000` `[VERIFIED]`.
     - `candidate_manifest.json:16`: `loader_entry` is pinned at `0x00008000` `[VERIFIED]`.
     - `candidate_loader.bin` at `0x81D8` (`my_restart` entry): prologue instruction `push {r3, lr}` consumes 8 bytes of stack `[VERIFIED]`.
     - At `main_prototype.c:51-52`, `w->loader_sp = current_sp;` stores `0x00008000 - 0x08 = 0x00007FF8` `[VERIFIED]`.
   - Prior contents at `0x0035F7A0` (new, `[VERIFIED]` by test `test_valid_loader_record_at_7a0_parsed_at_historical_780`): `candidate_main.bin` is embedded byte-for-byte in `candidate_loader.bin` at offset `0x280`. The core image bytes that `core_copy()` places at `0x0035F7A0..0x0035F7BF` are all zero, so a completed `core_copy()` zeroes the witness slot before the eight witness stores. That `core_copy()` copies exactly this embedded blob is `[INFERRED]` from `main_prototype.c:33-38` and the byte-identical embedding.
2. **Core Writer**:
   - Source: `chdk-port/platform/g3x/sub/110c/boot_prototype.c:26-56` `[VERIFIED]`.
   - Structure Instance: `volatile boot_witness_t boot_witness __attribute__((aligned(16), section(".data")))` placed at `0x0035F7A0` in `candidate_port2a/candidate_main.elf` `[VERIFIED]`.
   - Transitions:
     - `witness_record_core()` (`boot_prototype.c:32-43`): `stage_state` `0x01` → `0x03`, sets `core_entry_pc = 0x003489B5`, recomputes checksum `[VERIFIED]`.
     - `witness_record_continuation()` (`boot_prototype.c:45-56`): `stage_state` `0x03` → `0x07`, sets `cont_tick = 0x0014F200`, recomputes checksum `[VERIFIED]`.

### 2.2 The Witness Inspector (code path)
1. **Canon Basic Script**:
   - Source: `firmware/tools/witness_inspector_gm110c.m`. The build copies it unchanged to `candidate_port2a/witness_inspector_gm110c.m` (`tools/build_candidate_port2a.py:825`). The two files are byte-identical (asserted in `test_historical_vs_regenerated_payload_target_addresses`) `[VERIFIED]`.
   - Allocates `payload_size + 4` bytes, reads `A/WITNESS.BIN` and requires exactly 444 bytes (`.m:26, 93, 109-111`). It flushes L1 caches (`0xFC127A85`, `0xFC127B2B`, `.m:127-128`) and calls `buf + 1` with `h_title`, `h_status`, `expected_nonce = 0` (`.m:28, 136`) `[VERIFIED]`.
   - **The script performs no address or hash check on `WITNESS.BIN`. It accepts either 444-byte payload** (`.m:26-28, 109-111`; there is no `F780`/`F7A0` literal in the script, asserted by test) `[VERIFIED]`.
2. **Native Assembly Payload**:
   - Source: `firmware/tools/witness_inspector_payload.S`. The target address is set at assembly time by `movw r7, #:lower16:BOOT_WITNESS_ADDR` / `movt r7, #:upper16:BOOT_WITNESS_ADDR` (`payload.S:54-58`). The source has no default address: it fails with `#error` if `BOOT_WITNESS_ADDR` is not defined. **The address a given `.bin` reads depends on how it was assembled (Section 2.3)** `[VERIFIED]`.
   - Reads exactly the 8 words `[r7+0x00 .. r7+0x1C]`, verifies magic, version, checksum and stage mask, and updates LCDMsg text and colours (`payload.S:61-197`) `[VERIFIED]`.
3. **Reference Host Validator & Emulation**:
   - `tools/validate_witness_inspector.py:242-273` (`emulate_inspector_parse`), `:131-178` (`extract_witness_addr_from_binary_bytes`, the MOVW/MOVT decoder for raw `.bin`), `:228-239` (`read_address_metadata`); and `tools/validate_boot_witness.py:45-138` (`inspect_witness`) `[VERIFIED]`.

### 2.3 Inspector Provenance: Tracked Historical Payload vs Regenerated Payload

#### (i) Tracked historical payload `firmware/tools/witness_inspector_payload.bin` `[VERIFIED]`
| Property | Value | Citation |
|---|---|---|
| Git status | Tracked (`git ls-files firmware/tools`); last changed in commit `5d644cb` | `git log -- firmware/tools/witness_inspector_payload.bin` |
| Size | 444 B | test `test_historical_vs_regenerated_payload_target_addresses` |
| SHA-256 | `f1cd6438b8c54a233b28360705c02f869da2149c6499e9b2d8c340746a3c7f00` | `docs/REPRODUCIBILITY_MANIFEST.md:83`; `docs/PORT16_CANDIDATE_BUILD.md:389`; `reference/candidate_port2a_precorrection/candidate_manifest.json:69`; recomputed by test |
| MOVW/MOVT bytes at `0x0A..0x11` | `4ff28077 c0f23507` = `movw r7, #0xF780; movt r7, #0x0035` | `docs/PORT16_CANDIDATE_BUILD.md:327`; test |
| Address decoded by the real decoder | **`0x0035F780`** | `tools/validate_witness_inspector.py:131-178`; test |
| Metadata file | `firmware/tools/witness_inspector_metadata.json:4-5` = `0x0035F780` / `3536768`; `:7` `payload_bin` = `firmware/tools/witness_inspector_payload.bin` | file; parsed by `vwi.read_address_metadata` in test |
| Role | Pre-correction baseline (pre-PORT-16 candidate placed `boot_witness` at `0x0035F780`) | `docs/PORT16_WITNESS_ADDRESS.md:17-28, 233-237`; `docs/HANDOFF.md:2078-2080` |

#### (ii) Inspector generated by the current build tooling `candidate_port2a/witness_inspector_payload.bin` `[VERIFIED]`
| Property | Value | Citation |
|---|---|---|
| Git status | Not tracked (`git ls-files candidate_port2a` is empty); it is a `candidate_build` output | — |
| How generated | Default path `generate_candidate_inspector()` assembles `payload.S` with `-DBOOT_WITNESS_ADDR=0x0035F7A0`, the address read from the ELF symbol, and verifies the binding fail-closed. The alternative `--use-existing-inspector` path (`copy_inspector_artifacts`) also verifies against `0x0035F7A0` fail-closed, so it would reject the tracked `0x0035F780` payload | `tools/build_candidate_port2a.py:54, 460, 792-854, 857-885, 1026-1035` |
| Size | 444 B | test |
| SHA-256 | `241420a6eea2d7cbedd14046ec4f5988ed0404c5a82bb5d2ed6693fd74e612e2` | `candidate_port2a/candidate_manifest.json:69`; `docs/PORT16_CANDIDATE_BUILD.md:364`; `docs/PORT16_OWNER_TRIAL_PLAN.md:35, 130`; recomputed by test |
| MOVW/MOVT bytes at `0x0A..0x11` | `4ff2a077 c0f23507` = `movw r7, #0xF7A0; movt r7, #0x0035` | `docs/PORT16_CANDIDATE_BUILD.md:337`; test |
| Address decoded by the real decoder | **`0x0035F7A0`** | `tools/validate_witness_inspector.py:131-178`; test |
| Metadata file | `candidate_port2a/witness_inspector_metadata.json:4-5` = `0x0035F7A0` / `3536800` | build output; parsed in test |

The two payloads differ in **exactly one byte**: offset `0x0C`, `0x80` vs `0xA0`, the low byte of the `movw` immediate. They have the same size, and the same script loads either without error (`[VERIFIED]` by test).

#### (iii) Which payload the owner ran: `[UNKNOWN]`
- The trial instructions told the owner to copy the regenerated payload and **not** the `firmware/tools/` one (`docs/PORT18_OWNER_TRIAL_PLAN.md:201-202`; `docs/PORT19_GO_NOGO.md:152`; `docs/PORT16_OWNER_TRIAL_PLAN.md:130`) `[VERIFIED that this was instructed]`.
- No tracked trial artifact records the SHA-256, size or MOVW/MOVT bytes of the `WITNESS.BIN` that was on the card during O6. No card listing or photo-to-hash record exists in the repository either. Searches for both hashes in tracked files found only build and plan documents, no trial record. **So the exact payload and address the owner ran are `[UNKNOWN]`.**
- `tools/validate_witness_inspector.py:71-75` falls back silently to the `firmware/tools/` artifacts when `candidate_port2a/` is missing. This is a host-validation default, not evidence about the card `[VERIFIED code; relevance INFERRED]`.

#### (iv) Consequence (candidate explanation, `[INFERRED]`, T4 must rule out)
If the owner ran the `0x0035F780` payload, the `WITNESS_INVALID / INVALID / CORRUPT` reading comes from the 32 bytes at `0x0035F780..0x0035F79F`. It does not come from the LOADER record at `0x0035F7A0`. The window ends exactly where the record begins, so the record cannot influence the result. In that case **O6 says nothing about H2, H3 or H4**: the loader may have written a valid LOADER record, and O6 would look exactly the same.

Host evidence (`[VERIFIED]` by test `test_valid_loader_record_at_7a0_parsed_at_historical_780`): with a valid LOADER record at `0x0035F7A0`, the parse at `0x0035F780` reports `WITNESS_INVALID / INVALID / CORRUPT`, sentinel `0x574954EE`, colours `3, 3`. This holds for every modelled content of `0x0035F780`:
- the bytes `core_copy()` leaves there: `3600372e3100382e3000392e300031302e300031312e3000 0300000000000000`, an ASCII-like table `"6\0" "7.1\0" "8.0\0" "9.0\0" "10.0\0" "11.0\0"` followed by `0x00000003 0x00000000`, from `candidate_main.bin` offset `0x16DCC`;
- all zeros;
- stock-like pointers;
- `0xFF` fill.

The parse at `0x0035F7A0` on the same memory reports `LOADER_REACHED`.

This explanation would also fit **any** outcome of the loader write, so O6 cannot test it. Evidence the owner can check to settle it, all host-side and read-only:
1. SHA-256 of `WITNESS.BIN` on the card used for O6: `f1cd6438…` means it read `0x0035F780`; `241420a6…` means it read `0x0035F7A0`.
2. Or the bytes at file offset `0x0A..0x11` of that `WITNESS.BIN`: `4ff28077c0f23507` means `0x0035F780`; `4ff2a077c0f23507` means `0x0035F7A0`. Any other value means a third, unaccounted payload.
3. Its size (must be 444 B, otherwise the script would have shown `ERR_READ`, not O6), and the SHA-256 of `extend.m` on the card. The two tracked copies are identical, so this only confirms the script.
4. The host shell history or file timestamps of the copy step, if retained.

---

## 3. Field-by-Field Writer vs Inspector Parser Comparison

| Field | Byte Offset | Loader Writer (`main_prototype.c`) | Core Writer (`boot_prototype.c`) | Inspector Parser (`payload.S` & `vwi.py`) | Status | Citation |
|---|---|---|---|---|---|---|
| **`magic`** | `0x00` (Word 0) | Writes `BOOT_WITNESS_MAGIC` (`0x5749544E`, `"WITN"`) | Checked unchanged at transitions (`lines 34, 47`) | `ldr r0, [r7, #0]`; compares to `0x5749544E`; branches to `.Lstate_invalid` if mismatch | **MATCH (`[VERIFIED]`)** | `main_prototype.c:43`; `boot_witness.h:8`; `payload.S:61-65`; `vwi.py:85, 250` |
| **`version`** | `0x04` (Word 1) | Writes `BOOT_WITNESS_VERSION` (`0x00010001`, v1.1) | Checked unchanged at transitions (`lines 35, 48`) | `ldr r0, [r7, #4]`; compares to `0x00010001`; branches to `.Lstate_invalid` if mismatch | **MATCH (`[VERIFIED]`)** | `main_prototype.c:44`; `boot_witness.h:9`; `payload.S:67-71`; `vwi.py:86, 250` |
| **`session_nonce`** | `0x08` (Word 2) | Writes `0x32A80001` (GM1.10C challenge nonce) | Unchanged across core transitions | Passed `expected_nonce = 0` by script; if `expected_nonce == 0` or `0x32A80001`, skips challenge check | **MATCH (`[VERIFIED]`)** | `main_prototype.c:48`; `inspector_gm110c.m:28, 136`; `payload.S:101-108`; `vwi.py:259` |
| **`stage_state`** | `0x0C` (Word 3) | Writes `STAGE_LOADER` (`0x01`) | Core writes `0x03` (`STAGE_LOADER \| STAGE_CORE`); Continuation writes `0x07` (`0x01 \| 0x02 \| 0x04`) | Evaluates `stage_state`: `1 -> .Lstate_loader`, `3 -> .Lstate_core`, `7 -> .Lstate_continuation`, else `.Lstate_invalid` | **MATCH (`[VERIFIED]`)** | `main_prototype.c:50`; `boot_prototype.c:39, 52`; `payload.S:117-129`; `vwi.py:264-273` |
| **`loader_sp`** | `0x10` (Word 4) | Writes current `sp` (`asm("sp")`), `0x00007FF8` | Unchanged by core | Not checked at Stage 1 or 2; at Stage 3, requires 8-byte alignment (`loader_sp % 8 == 0`) | **MATCH (`[VERIFIED]`)** | `main_prototype.c:51-52`; `entry.S:7`; `payload.S:161-163`; `vwi.py:269` |
| **`core_entry_pc`** | `0x14` (Word 5) | Writes `0` | Core writes `0x003489B5` (Thumb bit set for `MEMISOSTART`) | Not checked at Stage 1 or 2; at Stage 3, requires exact match `core_entry_pc == 0x003489B5` | **MATCH (`[VERIFIED]`)** | `main_prototype.c:53`; `boot_prototype.c:40`; `payload.S:154-159`; `vwi.py:269` |
| **`cont_tick`** | `0x18` (Word 6) | Writes `0` | Continuation writes `0x0014F200` | Checked only as part of checksum computation | **MATCH (`[VERIFIED]`)** | `main_prototype.c:54`; `boot_prototype.c:53`; `boot_witness.h:41`; `payload.S:80-87` |
| **`checksum`** | `0x1C` (Word 7) | `compute_witness_checksum()` over first 7 words | Recomputed at each core transition | Loops 7 words (offsets `0x00..0x18`), accumulates `c = (c * 31) ^ w`, compares with offset `0x1C` | **MATCH (`[VERIFIED]`)** | `boot_witness.h:33-43`; `payload.S:75-92`; `vwi.py:96-100, 254-256` |
| **Record Size** | N/A | `sizeof(boot_witness_t) == 32` (8 x 4B words) | 32 bytes (`aligned(16)`) | Reads 8 32-bit words (32 bytes) at `r7` (`payload.S:57-90`); reference emulator unpacks 32 bytes (`<IIIIIIII`) with host-API `len(buf) >= 32` check (`vwi.py:244-247`) | **MATCH (`[VERIFIED]`)** | `boot_witness.h:30`; `payload.S:57-90`; `vwi.py:244-247` |
| **Record Address** | N/A | `0x0035F7A0` (`build_candidate_port2a.py:506`) | `boot_witness` in `.data` at `0x0035F7A0` | Regenerated payload: `0x0035F7A0`. **Tracked `firmware/tools` payload: `0x0035F780`** (Section 2.3) | **MATCH for regenerated payload; MISMATCH (−0x20) for tracked payload (`[VERIFIED]`); which one ran: `[UNKNOWN]`** | `build_candidate_port2a.py:54, 506, 812`; `firmware/tools/witness_inspector_metadata.json:4`; `vwi.py:131-178` |
| **Endianness** | N/A | ARMv7-R Cortex-R4 Little-Endian | ARMv7-R Cortex-R4 Little-Endian | Little-Endian struct read / unpack (`<IIIIIIII`) | **MATCH (`[VERIFIED]`)** | `entry.S`; `main_prototype.c`; `payload.S:39-41`; `vwi.py:247` |

### 3.1 Checksum Algorithm and Coverage Verification
- **Formula**:
  $$\text{checksum} = c_7, \quad \text{where } c_0 = \text{0x55AA55AA}, \quad c_{k+1} = (c_k \times 31) \oplus w_k \quad (k \in 0..6)$$
- **Coverage**: Exactly the 7 32-bit words: `magic`, `version`, `session_nonce`, `stage_state`, `loader_sp`, `core_entry_pc`, and `cont_tick` `[VERIFIED]`.
- For the loader-only record with `loader_sp = 0x00007FF8`, the exact checksum is **`0x3028882D`** (host C probe compiled against the real `boot_witness.h`) `[VERIFIED]`.
- **Record-format Writer / Parser Mismatch**: **None** `[VERIFIED]`. The only mismatch found is the *address* mismatch of the tracked historical payload (Section 2.3). That is a provenance issue, not a record-format bug. It is documented, not fixed.

---

## 4. Failure Mapping to `WITNESS_INVALID` / `INVALID / CORRUPT`

`firmware/tools/witness_inspector_payload.S:190-197` (`.Lstate_invalid`) is the only place that loads `str_title_inv` ("WITNESS_INVALID", `:254`) and `str_corrupt` ("INVALID / CORRUPT", `:261`) `[VERIFIED]`. The title and status therefore always appear together:

```text
.Lstate_invalid:
    Title String:     "WITNESS_INVALID"
    Status String:    "INVALID / CORRUPT"
    Title Color:      3
    Status Color:     3
    Return Sentinel:  0x574954EE (SENTINEL_INVALID)
```

### 4.1 Native Payload vs Reference Emulator Behavior
- **Native Assembly Inspector** (`payload.S:57-90`): no buffer pointer or length argument; reads 8 words at the address fixed in `r7` at assembly time. It cannot detect truncation `[VERIFIED]`.
- **Python Reference Emulator** (`vwi.py:244-245`): `len(buf) < 32` returns `SENTINEL_INVALID`. This is a host-API guard only and is not a physical memory state `[VERIFIED]`.

---

## 5. Which Raw Memory States Give Exactly `WITNESS_INVALID / INVALID / CORRUPT`

Observed O6: `WITNESS_INVALID / INVALID / CORRUPT`, sentinel `0x574954EE` `[VERIFIED that it is recorded: docs/PORT18_OWNER_TRIAL_PLAN.md:267, 288]`.

### 5.1 `[VERIFIED]` Exact Rejection Predicates in the Parser
Let `W[0..7]` be the 8 little-endian words read at the payload's `r7` address (`0x0035F780` or `0x0035F7A0` depending on the payload, Section 2.3). The script passes `expected_nonce = 0` (`.m:28, 136`), so the stale branch `.Lstate_stale` cannot be reached (`payload.S:101-102`; `vwi.py:259`). The parser then returns `WITNESS_INVALID / INVALID / CORRUPT` **if and only if** at least one of the following predicates holds, checked in this order:

| # | Predicate | Native payload | Reference emulator |
|---|---|---|---|
| P1 | `W[0] != 0x5749544E` (magic) | `payload.S:61-65` | `vwi.py:250-251` |
| P2 | `W[1] != 0x00010001` (version) | `payload.S:67-71` | `vwi.py:250-251` |
| P3 | `W[7] != C(W[0..6])`, where `C` = checksum of Section 3.1 | `payload.S:75-92` | `vwi.py:254-256` |
| P4 | `W[3] ∉ {1, 3, 7}` (stage mask) | `payload.S:117-129` | `vwi.py:264-273` |
| P5 | `W[3] == 7` and `W[5] != 0x003489B5` | `payload.S:152-158` | `vwi.py:268-270` |
| P6 | `W[3] == 7` and `(W[4] & 7) != 0` | `payload.S:160-163` | `vwi.py:268-270` |
| (host only) | `len(buf) < 32` | not applicable | `vwi.py:244-245` |

If none holds, the result is `LOADER_REACHED` (`W[3]==1`), `CORE_REACHED` (`W[3]==3`) or `CONT_ATTEMPTED` (`W[3]==7`) (`payload.S:132-177`; `vwi.py:264-271`). `W[2]` (nonce) and, for stages 1 and 3, `W[4..6]` affect the result only through P3.

### 5.2 `[VERIFIED by test]` Byte Patterns Actually Tested
All results come from `vwi.emulate_inspector_parse(buf, expected_nonce=0)` in `tests/test_port21_witness_roundtrip.py`. "INVALID" means `(0x574954EE, "WITNESS_INVALID", "INVALID / CORRUPT", 3, 3)`.

| Tested 32-byte window | Result | Predicate hit | Test |
|---|---|---|---|
| Loader-only record from host C probe (`…7FF8…`, cs `0x3028882D`) | `LOADER_REACHED` / `FRESHNESS_UNVERIFIED`, `0x57495401`, `1,4` | none | `test_real_c_writer_bytes_roundtrip` |
| Same, `expected_nonce = 0x32A80001` | `LOADER_REACHED` | none | `test_real_c_writer_bytes_roundtrip` |
| All zero `00×32` | INVALID | P1 | `test_all_zero_region_yields_witness_invalid` |
| Stock-like pointers (`0x0012BBE0, 0x00015DA4, 0xFC77C8B0, …, 0x003489B4`) | INVALID | P1 | `test_overwritten_stock_boot_data_yields_witness_invalid` |
| ASCII `"DryOS version 2.3, release 0059"` | INVALID | P1 | same |
| `FF×32`, `AA×32`, `55×32`, `DEADBEEF×8` | INVALID | P1 | same |
| Correct magic, version `0x00020000` | INVALID | P2 | same; `test_exhaustive_rejection_modes_mapping_to_witness_invalid` |
| Correct magic+version, nonce `0x12345678`, stage 1, checksum `0` | INVALID | P3 | `test_overwritten_stock_boot_data_yields_witness_invalid` |
| Magic `0xDEADBEEF` | INVALID | P1 | `test_exhaustive_rejection_modes_mapping_to_witness_invalid` |
| Valid stage-3 record, 1 bit flipped in checksum / in byte 0 | INVALID | P3 / P1 | same |
| Stage `0x00`, `0x02`, `0x04`, `0x05` with matching checksum | INVALID | P4 | same |
| Stage 7, `core_entry_pc = 0x003489B4` | INVALID | P5 | same |
| Stage 7, `loader_sp = 0x7FF9` | INVALID | P6 | same |
| 31-byte buffer (host API only) | INVALID | host only | same |
| Valid stage 1 / 3 / 7 records | `LOADER_REACHED` / `CORE_REACHED` / `CONT_ATTEMPTED` | none | `test_valid_records_across_all_stages` |
| Window at `0x0035F780` with valid LOADER record at `0x0035F7A0`; `0x780` contents = core image bytes, zero, stock pointers or `FF` | INVALID (for all four) | P1 | `test_valid_loader_record_at_7a0_parsed_at_historical_780` |
| Window at `0x0035F7A0` of the same memory | `LOADER_REACHED` | none | same |
| Prior valid LOADER record (sp `0x7FF8`) + only first 3 loader stores (reviewer example) | **`LOADER_REACHED`** | none | `test_prior_valid_record_plus_partial_rewrite_is_loader_reached` |
| First *n* of 8 loader stores (source order `main_prototype.c:43-55`), *n* = 0..8, over prior contents: | | | `test_partial_write_status_by_prior_contents` |
| · prior valid LOADER (sp `0x7FF8`) | `LOADER_REACHED` for every *n* | none | |
| · prior valid LOADER (sp `0x7FF0`) | `LOADER_REACHED` for *n* ≤ 4; INVALID for *n* = 5..7; `LOADER_REACHED` for *n* = 8 | P3 | |
| · prior valid `CONT_ATTEMPTED` | `CONT_ATTEMPTED` for *n* ≤ 3; INVALID for *n* = 4..7; `LOADER_REACHED` for *n* = 8 | P3 | |
| · prior all zero (also what `core_copy()` leaves at `0x0035F7A0`) | INVALID for *n* ≤ 7; `LOADER_REACHED` for *n* = 8 | P1/P2/P3 | |
| · prior `FF×32` | INVALID for *n* ≤ 7; `LOADER_REACHED` for *n* = 8 | P1/P2/P3 | |

### 5.3 `[INFERRED]` Physical Causes That Could Produce These Byte Patterns (not exhaustive)
None of these causes was observed. The list is illustrative, not complete; other causes may exist.
1. **Wrong inspector address**: the owner ran the tracked `0x0035F780` payload. The window then holds whatever was at `0x0035F780`: core-image data after `core_copy()`, stock data, or zeros. All four modelled contents hit P1. This explanation fits regardless of what the loader did (Section 2.3 (iv)).
2. **Witness never written**: the loader did not run, or it stopped before `main_prototype.c:43`. The window holds whatever was there before: zeros or stock data (P1 for every tested pattern of this kind). If `core_copy()` completed but the stores did not, the slot is zero (P1).
3. **Witness written, later overwritten** by stock firmware after a reset or by other writers: P1 to P4 depending on the new data.
4. **Partial or aborted write**: this **may or may not** produce INVALID. It depends on what the remaining bytes held before the write (Section 5.2):
   - over zeros or unrelated data, any prefix of fewer than 8 stores is INVALID;
   - over an identical prior record, any prefix stays `LOADER_REACHED`;
   - over a prior record that differs, the result depends on which fields differ and how many stores landed.

   In the as-built sequence, a completed `core_copy()` zeroes the slot first (Section 2.1). A prior record would then survive into a partial write only if `core_copy()` did not complete, or if the stores reached cache but not DRAM. Both conditions are `[UNKNOWN]`.
5. **Write not visible to the reader**: for example, data cache contents lost on reset before writeback. The reader then sees the prior DRAM contents (any of the above).
6. **Bit corruption** of an otherwise valid record: P1 to P3 for single-bit flips in the tested positions.

### 5.4 Consistency with H1–H4 `[INFERRED]`
| Hypothesis | Byte patterns at the window that fit O6 | Notes |
|---|---|---|
| **Address explanation** (tracked payload ran) | Anything at `0x0035F780` failing P1–P6, including the core image bytes there | O6 then carries no information about H1 to H4. Settle with the `WITNESS.BIN` hash (Section 2.3 (iv)). |
| **H1** `StartDiskboot` never reached the loader | Prior contents of `0x0035F7A0`: zeros or stock data | Fits O6 if those contents fail P1–P6. They would not fail if a valid record survived from an earlier boot (`[UNKNOWN]`). |
| **H2** Loader ran but stopped before or during the witness write | Zeros after `core_copy()`, or a partial prefix over prior contents | INVALID in most tested cases, but not when the prior contents already formed a valid record (Section 5.2). |
| **H3** Witness written, later overwritten | Overwrite data failing P1–P4 | — |
| **H4** Record malformed as built | — | **Not supported** for the code as built: the as-built record parses as `LOADER_REACHED` at its own address `[VERIFIED]`. A runtime malformation (cache, fault mid-write) is cause 4 or 5 above, not a format bug. |

### 5.5 Summary
1. The loader witness record as built is **not malformed**. Read at `0x0035F7A0`, it parses as `LOADER_REACHED` (`0x57495401`), and a loader-only record is reported as valid `[VERIFIED]`.
2. `WITNESS_INVALID / INVALID / CORRUPT` is produced exactly when the 32-byte window read by the payload satisfies P1 ∨ P2 ∨ P3 ∨ P4 ∨ P5 ∨ P6 `[VERIFIED]`.
3. The payload and window the owner used are `[UNKNOWN]`. If it was the tracked `0x0035F780` payload, O6 does not bear on H2, H3 or H4 `[INFERRED]`. T4 must check the card's `WITNESS.BIN` hash first.
4. RAM contents during O6 and whether the loader ran are `[UNKNOWN]`.

---

## 6. Display Color Analysis: Colour Index 3 and Rendering Context

### 6.1 Inspector Failure Color Index Selection (`[VERIFIED]`)
- `firmware/tools/witness_inspector_payload.S:193-194`: `.Lstate_invalid` sets `r6 = 3` and `r7 = 3` (title and status colour). The source comment says "Color 3 = Red".
- `tools/validate_witness_inspector.py:245, 251, 256, 270, 273`: every failure exit returns colours `3, 3`.
- Both payload binaries (Section 2.3) differ only in the `movw` immediate byte, so they select the same colours `[VERIFIED]`.

### 6.2 Palette Format and What Light Blue Means
- **Palette Format**: GM1.10C palette entries are 32-bit `AYCrCb`, not RGB (`docs/HDMI001_OVERLAY_PIPELINE.md:98`) `[VERIFIED: as documented there]`.
- **Physical colour of index 3**: depends on the active palette (`0x00015DB4`), the output device (LCD or HDMI), and the SCM state (`docs/HDMI001_OVERLAY_PIPELINE.md:76, 97`). Whether index 3 renders as red or light blue on this camera is `[UNKNOWN]` without a frame capture.
- **Significance**:
  - For the inspector's logic and verdict, the colour **means nothing** `[VERIFIED]`. The branch logic, strings, sentinel and colour indices are fixed in the payload and do not depend on how the palette renders.
  - For interpretation: the text `WITNESS_INVALID / INVALID / CORRUPT` alone identifies `.Lstate_invalid`. Light blue for index 3 most likely reflects the active palette rather than a different code path, because no other path uses index 3 (`payload.S:135-136, 145-146, 173-174, 183-184, 193-194`) `[INFERRED]`. The plan's "(Red/Red)" label (`docs/PORT18_OWNER_TRIAL_PLAN.md:267`) comes from the source comment, not from a measured colour `[INFERRED]`. The colour cannot tell the two payloads apart `[VERIFIED]`.

---

## 7. Host Test Suite Summary (`tests/test_port21_witness_roundtrip.py`)

Run with `python3 -m unittest -v tests.test_port21_witness_roundtrip` (11 tests, offline, no ROM, no camera).
- `test_real_c_writer_bytes_roundtrip`: host C probe with the real `boot_witness.h` and the loader's assignments. Checks `sizeof`/`offsetof` and the checksum `0x3028882D`, then parses the bytes → `LOADER_REACHED`.
- `test_disassembly_coherence_and_sp_provenance`: entry SP, `push {r3, lr}`, `str.w sp, [r1, #16]` and the `0x0035F7A0` literal in `candidate_loader.bin` (plus objdump when available).
- `test_all_zero_region_yields_witness_invalid`, `test_overwritten_stock_boot_data_yields_witness_invalid`, `test_exhaustive_rejection_modes_mapping_to_witness_invalid`: P1–P6 and host-only truncation → INVALID.
- `test_valid_records_across_all_stages`: stages 1/3/7.
- `test_color_index_3_selection_and_rendering_invariance`: colour index 3 on the invalid path.
- `test_historical_vs_regenerated_payload_target_addresses` (new): checks the SHA-256 of both payloads, and decodes `0x0035F780` vs `0x0035F7A0` with the real decoder and both metadata files. Asserts the one-byte difference, and that the script is identical and checks only the size.
- `test_valid_loader_record_at_7a0_parsed_at_historical_780` (new): valid LOADER record at `0x0035F7A0`, parse at the tracked payload's decoded address `0x0035F780` → INVALID (`0x574954EE`, `3,3`) for core-image, zero, stock and `FF` fills; parse at `0x0035F7A0` → `LOADER_REACHED`.
- `test_prior_valid_record_plus_partial_rewrite_is_loader_reached` (new): reviewer example → `LOADER_REACHED`.
- `test_partial_write_status_by_prior_contents` (new): the status table of Section 5.2 for *n* = 0..8 stores.

No candidate, loader, inspector or PORT-20 source was changed. The tests read `candidate_port2a/` build outputs, so `candidate_build` must have run first.
