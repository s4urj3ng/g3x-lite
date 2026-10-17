# Canon Basic activation investigation — G3 X `GM1.10C`

Updated: 2026-10-17  
Scope: static analysis and public-source research only. No SD-card or camera changes were made during this investigation.

## Executive finding

Canon Basic is supported on the PowerShot G3 X family, including documented successful use on `1.00C` and a model-specific script on `GM1.10E`. The failed `GM1.10C` attempt does **not** disprove interpreter support.

The strongest diagnostic fact is the Universal Dumper's order of operations: it initializes event procedures, attempts to create/truncate `A/CBDUMPER.LOG`, and appends `Started` **before** probing any candidate ROM address. Since neither `CBDUMPER.LOG` nor `PRIMARY.BIN` appeared, a wrong `GM1.10C` ROM address is not the leading explanation. Failure most likely occurred before or during script activation, event-procedure registration, or the first SD write.

The `No images` screen is not an activation failure indicator. Historical reports show Canon Basic status text can be black or otherwise invisible on that screen while the output files are still written. Here, absence of the two files—not absence of visible text—is the meaningful observation.

## Evidence supplied for this attempt

These are treated as user-verified observations, not independently repeated in this session:

- Camera: Canon PowerShot G3 X, `GM1.10C`, platform ID `0x32A8`.
- Card: 64 GB SDXC, MBR with a FAT32 partition.
- Root request file: `script.req`, 17 bytes, `for DC_scriptdisk`.
- Dumper: repository `firmware/tools/extend.m`, SHA-256 `3ca970ba22c2e9b50cf84bfc1f63074c84b01808129e0f1fbf6af25e4b362da5`.
- FAT32 partition VBR: ASCII `SCRIPT` at byte offset `0x1F0`.
- Camera entered Playback and displayed `No images`; pressing `FUNC./SET` produced no visible response.
- No `PRIMARY.BIN` or `CBDUMPER.LOG` was created.
- The VBR remained byte-identical after the attempt.

The unchanged VBR is expected: executing Canon Basic should read the `SCRIPT` marker, not rewrite it. It confirms the attempt did not alter that sector, but does not prove the firmware accepted the volume as a script disk.

## 1. Is Canon Basic supported on G3 X / DIGIC 6?

### Verified

1. The CHDK Canon Basic documentation says the scripting system exists on DryOS cameras, with model-dependent available functions. It is Canon firmware functionality and does not require CHDK. Source: [CHDK Wiki — Canon Basic](https://chdk.fandom.com/wiki/Canon_Basic), archived primary snapshot [`20240527012744`](https://web.archive.org/web/20240527012744id_/https://chdk.fandom.com/wiki/Canon_Basic), retrieved 2026-10-17.
2. G3 X owner Nippey reported successfully dumping G3 X `1.00C` and obtaining `PRIMARY.BIN (32MB)` and `CBDUMPER.LOG`; srsa_4c replied that the dump looked correct. Sources: [forum post 124672](https://chdk.setepontos.com/d/12600-g3-x-100c-fw-dump/1), 2015-09-15T07:38:39Z, and [post 124678](https://chdk.setepontos.com/d/12600-g3-x-100c-fw-dump/2), 2015-09-15T21:22:19Z, retrieved 2026-10-17.
3. Ranma published a G3 X `GM1.10E` Canon Basic script and gave the model-specific instruction: save it as root `extend.m`, prepare the card for scripts, start in Playback, and press SET. Source: [forum post 143433](https://chdk.setepontos.com/d/12600-g3-x-100c-fw-dump/18), 2020-05-11T11:03:54Z, retrieved 2026-10-17.
4. CHDK r5491 generated symbol lists contain `MakeScriptDisk_FW` for DIGIC 6 reference ports including G5 X and SX710 HS. This corroborates that script-disk support persisted in DIGIC 6 firmware, but it is not G3 X `GM1.10C` source. Source: [`platform/g5x/sub/100c/funcs_by_name.csv`](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/platform/g5x/sub/100c/funcs_by_name.csv) and [`platform/sx710hs/sub/100a/funcs_by_name.csv`](https://github.com/01luna/CHDK/blob/21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6/platform/sx710hs/sub/100a/funcs_by_name.csv), r5491 / `21b9a14eb2043aeffdd2cb141081e7dcfe75f7e6`, retrieved 2026-10-17.

### Unknown

- No `GM1.10C` ROM or Canon source is available to prove its exact Canon Basic dispatcher, event-procedure set, or accepted FAT volume geometry.
- Success on `1.00C` and `GM1.10E` makes removal from `GM1.10C` unlikely, but does not prove every entry point behaves identically.

## 2. Correct activation sequence and the `No images` state

The evidence-supported sequence is:

1. Use a FAT16 or FAT32 partition.
2. Put the six ASCII bytes `SCRIPT` at offset `0x1F0` of the **FAT partition's volume boot sector**, not the disk MBR.
3. Put `script.req` in the root, containing only `for DC_scriptdisk` (a trailing newline is accepted by the general wiki; the verified 17-byte form is valid).
4. Put `extend.m` in the root.
5. Start the camera in Playback mode.
6. Press the center `FUNC./SET` / SET button once after Playback is ready.
7. Restart the camera before retrying, because `extend.m` can generally be started only once per boot.

Sources: [CHDK Wiki — Canon Basic](https://chdk.fandom.com/wiki/Canon_Basic) and [Card Setup](https://chdk.fandom.com/wiki/Canon_Basic/Card_Setup), archived snapshots [`20240527012744`](https://web.archive.org/web/20240527012744id_/https://chdk.fandom.com/wiki/Canon_Basic) and [`20220129011254`](https://web.archive.org/web/20220129011254id_/https://chdk.fandom.com/wiki/Canon_Basic/Card_Setup), plus G3 X-specific post 143433 above. Retrieved 2026-10-17.

No authoritative source says that a photo must be present for `extend.m` to execute. Historical tests instead explain the display symptom:

- In the CHDK Canon Basic development thread, reyalp states that default message text can be black and invisible when there are no images or when the displayed area is dark. Source: [DryOS Basic scripting, post 24](https://chdk.setepontos.com/d/5549-dryos-basic-scripting/16), 2010-08-15, retrieved 2026-10-17.
- In a dumper troubleshooting report, the S95 showed `No Image`; the status text was visually obscured, yet `CBDUMPER.LOG` and `PRIMARY.BIN` were written successfully. Source: [How to Dump Firmware?, post 68 context](https://chdk.setepontos.com/d/17/68), retrieved 2026-10-17.
- The dumper page itself warns that status text may not be visible and instructs users to check `CBDUMPER.LOG` and `PRIMARY.BIN`. Source: [CHDK Wiki — Dumper](https://chdk.fandom.com/wiki/Canon_Basic/Scripts/Dumper), archived snapshot [`20240724053956`](https://web.archive.org/web/20240724053956id_/https://chdk.fandom.com/wiki/Canon_Basic/Scripts/Dumper), retrieved 2026-10-17.

Conclusion: **`No images` can hide status text, but does not prevent Canon Basic execution.** Taking a photo is not required by the documented activation contract.

## 3. SDXC/FAT32 and boot-sector requirements

### Verified

- Canon Basic documentation specifies FAT16 or FAT32 and `SCRIPT` at partition-VBR offset `0x1F0`; it does not specify an SDHC-only capacity ceiling. The marker is different from CHDK's `BOOTDISK` marker and must not be placed at the MBR or the CHDK FAT32 boot offset.
- A 64 GB card being SDXC does not inherently make its FAT32 structures invalid. The observed `No images` screen is consistent with the camera mounting the filesystem for playback.
- The supplied facts meet the documented marker and request-file byte requirements.

### Plausible but unverified

- The camera may mount a macOS-created 64 GB FAT32 volume for ordinary playback but reject it in the separate script-disk recognition path because of volume size, partition type, BPB geometry, or a firmware-specific check. The wiki says a card “may need to be low-level formatted in the camera first,” which makes format provenance a legitimate diagnostic variable. It does not prove this is the failure.
- A card lock tab or read-only mount could allow playback while preventing `CBDUMPER.LOG` and `PRIMARY.BIN`. The supplied facts do not state the lock-tab position or independently prove on-camera writeability during the attempt.

### Contradicted or unsupported

- “SDXC cannot run Canon Basic” is not established. The filesystem, not the marketing capacity class alone, is the documented requirement.
- “The boot sector stayed unchanged, so the script did not run” is false reasoning. No documented execution step writes the marker back.
- “No photos means FUNC./SET cannot trigger Canon Basic” is contradicted by historical successful file creation from a `No Image` screen.

## 4. Static audit of `extend.m`

Audited artifact: `firmware/tools/extend.m`, 123 lines, 2,689 bytes, pure 7-bit ASCII, SHA-256 `3ca970ba22c2e9b50cf84bfc1f63074c84b01808129e0f1fbf6af25e4b362da5` (reverified 2026-10-17).

### Control flow relevant to this failure

| Stage | Lines | Behavior | Diagnostic consequence |
|---|---:|---|---|
| Parse/load | whole file | Canon firmware must find and parse `extend.m`, then invoke `Initialize()` | A filename/path/parser failure leaves no files. |
| Procedure registration | 97–99 → 62–73 | Calls `System.Create()` and registers UI/debug procedures | A missing or incompatible procedure can stop before any log is opened. `GM1.10E` use supports but does not prove `GM1.10C`. |
| First filesystem action | 75–83 | Allocates 80 bytes, then opens `A/CBDUMPER.LOG` with `w` and closes it | If execution reaches this stage with writable storage and working Fut APIs, an empty log should exist even before ROM detection. |
| First logged marker | 100 via 85–95 | Reopens the log with `a`, writes `Started` and newline, closes it | A `Started` log would prove activation and successful initial setup. |
| ROM detection | 102 → 12–60 | Probes candidate signatures, including the DIGIC 6 `0xFC020004` check | Happens only after the log attempt. Wrong `GM1.10C` addresses cannot alone explain an absent log. |
| Dump | 104–121 | On a match, opens and writes `PRIMARY.BIN`; otherwise logs `not found!` | A clean address mismatch should still leave a log. |

### Early-failure paths

1. **Before `Initialize()`**: script disk not recognized, wrong root filename/path, trigger not accepted, once-per-boot state already consumed, or parse failure.
2. **Inside `RegisterProcs()`**: `System.Create`, `SystemEventInit`, or UI registration behavior differs or faults on `GM1.10C`.
3. **Inside `InitMsg()` before/at `Fopen_Fut`**: `LCDMsg_Create`, `AllocateMemory`, or file procedures are unavailable; or the card is not writable.
4. **During `GetStart()`**: an unmapped high-address probe could fault Candidate A before it reaches the DIGIC 6 probe. This is a real Candidate A risk, but because `Started` is closed first, it predicts a partial log unless earlier writes failed or were not persisted.

The script has no explicit firmware-version check and does not reference `GM1.10E`; therefore it cannot reject `GM1.10C` merely because the build suffix differs. It does assume event procedures and memory mapping that remain unverified on `GM1.10C`.

## 5. Ranked likely failure causes

1. **Script-disk activation was not accepted** — **most likely; medium confidence.** This best fits normal Playback behavior plus no log. Candidate sub-causes are the 64 GB non-camera-formatted FAT32 geometry/script-disk check, an unverified root-file detail at execution time, or the firmware not accepting the marker despite correct bytes.
2. **Trigger timing/state or once-per-boot behavior** — **medium confidence.** G3 X-specific evidence supports Playback + SET, but `extend.m` generally runs only once per boot. A press before the dispatcher was ready, an off-center control-wheel press, or retrying without a full power cycle can produce an apparent no-op.
3. **The card was readable but not writable on-camera** — **medium-low confidence.** This explains `No images` plus no output even if the script ran. Check the physical lock tab and ordinary camera write capability in a later approved experiment; neither was established in the supplied facts.
4. **`GM1.10C` aborts in `RegisterProcs()` or `InitMsg()`** — **medium-low confidence.** This occurs before the first reliable log marker. G3 X `GM1.10E` supports the same broad procedure family, but applying that fact to `GM1.10C` would be an assumption.
5. **Filename/path/parser mismatch despite the known source hash** — **low confidence.** The repository source itself is exact ASCII, but the on-card filename, case, root location, and bytes were not independently read in this session. A hidden extension or stale on-card copy would prevent activation.
6. **Candidate A faults on an earlier high-address `memcmp`** — **low for the observed two-file absence; still a real later risk.** It can explain failure to produce `PRIMARY.BIN`, but not normally the missing already-closed `Started` log.
7. **The `0xFC020004` DIGIC 6 signature or ROM size is wrong for `GM1.10C`** — **very low as the cause of this symptom.** A clean non-match leads to `not found!` in the log. No `GM1.10E` address should be assumed for `GM1.10C`, but this stage was probably never reached.

## 6. Safe, non-destructive diagnostic alternatives

- Re-read the on-card root directory and files on a computer: exact filenames, byte sizes, hashes, case, and absence of hidden extensions. Read-only.
- Re-read the partition table and VBR, including partition type, start LBA, FAT32 BPB, `SCRIPT` bytes, and VBR signature. Read-only.
- Confirm the physical card lock position without inserting it into the camera. No data change.
- Preserve a sector image and directory listing before any future trial so changes can be attributed precisely.
- Use a minimal file-marker Canon Basic probe instead of a ROM dumper in the next approved camera experiment. It avoids ROM-address reads and distinguishes activation/write setup from dumper logic.
- If the minimal probe works, statically evaluate the Improved Universal Dumper as a separate later candidate. Do not jump directly to it: changing both activation media and dumper logic at once would obscure the diagnosis.

## 7. Recommended next experiment — requires owner action

**Experiment:** after review and explicit approval, replace only `extend.m` on the same prepared card with a separately reviewed minimal Canon Basic probe that calls `System.Create()`, creates `A/CBPROBE.TXT`, writes a fixed short ASCII marker, closes it, and performs no memory reads, hardware-register access, firmware writes, or UI calls. Fully power-cycle the camera, start directly in Playback, wait for `No images`, press the center SET button once, wait 15 seconds, power off normally, and inspect the card on a computer.

This is recommended over immediately retrying the dumper because it isolates script activation + basic file writing from LCD procedures and all ROM-address assumptions.

### Risks

- Canon Basic execution is still on-camera code execution and needs explicit human approval under repository policy.
- The probe writes one small file to the SD card. Unexpected power loss could damage the filesystem, although it does not write camera firmware.
- `System.Create()` behavior is unverified on `GM1.10C`; a fault could shut down or restart the camera. Use a full battery and do not repeat automatically.

### Expected observations

- `CBPROBE.TXT` with the exact marker: script-disk activation, SET trigger, `System.Create`, and basic Fut file writing work. The failure is then narrowed to Candidate A's UI/allocation/ROM-detection path.
- No marker, camera otherwise normal: failure remains in card recognition, trigger state, parsing, procedure setup, or write access. Do not proceed to the dumper.
- Camera shuts down, restarts, freezes, or displays `ASSERT`/`FAILED`: record the exact behavior and stop. This supports a parser/procedure incompatibility and rules out further blind retries.

### Stopping conditions

- Stop after one attempt regardless of result.
- Stop immediately for abnormal heat, repeated restart, freeze, error message, or unexpected card activity beyond 30 seconds.
- Do not use `GM1.10E` addresses, try GPIO/LED diagnostics, switch to Candidate B, reformat media, or repeat the ROM dump until this result has been reviewed.

## 8. Comparison with existing repository research

### Confirmed

- `E038` correctly records the general FAT16/FAT32 marker, request file, Playback, and SET sequence.
- `E039`/`E041` correctly identify the audited Universal Dumper bytes and DIGIC 6 branch.
- `RISK-04` correctly treats 64 GB FAT32 as an unresolved compatibility variable, not a proven failure.
- The prohibition on carrying `GM1.10E` addresses into `GM1.10C` remains correct.

### Refined

- Existing preflight work treated the card setup as ready, but the failed attempt shows that correct static bytes do not prove the camera's script-disk dispatcher accepted this particular 64 GB volume.
- Existing `RISK-01` emphasized a high-address `memcmp` fault. That remains possible for dump failure, but Candidate A writes `Started` first; it is not the best explanation for an entirely absent log.
- Existing notes mention a zoom-lever fallback for touchscreen cameras. The G3 X has a physical SET button and ranma's G3 X-specific instruction says SET. There is no primary evidence that G3 X uses the touchscreen-only zoom-lever trigger, so it should not be the next experiment.
- The prior statement that Candidate A's exact lineage was “proven” on G3 X `1.00C` is too strong. Post 124672 proves a 32 MB dump and `CBDUMPER.LOG`, while the nearby wiki snapshot proves Candidate A existed; it does not identify the exact bytes Nippey executed.

## Conclusion

The present evidence supports Canon Basic capability on G3 X but does not prove successful activation on this `GM1.10C` attempt. The missing log moves the diagnostic boundary ahead of ROM detection. The next useful evidence should come from one minimal, reviewed marker-file probe—not from substituting `GM1.10E` addresses, adding visible-output assumptions, or repeating the full dumper blindly.

## 9. Candidate P1 — minimal activation probe

Status: **prepared and statically reviewed; not copied to SD and not executed**.  
Repository path: `firmware/tools/cbasic_activation_probe.m`  
Required on-card name if separately approved later: `extend.m`  
SHA-256: `ffea8a5aa7a5d17e9fc0191c1552b77cc45ae0cdb9dfe7b90b7c908034191ea5`  
Size: 303 bytes, 13 LF-terminated lines, pure 7-bit ASCII.

### Complete source

```basic
' Canon Basic activation and SD write probe
' Expected output: A/CBPROBE.TXT

DIM probe_file=0

private sub Initialize()
	System.Create()
	probe_file = Fopen_Fut("A/CBPROBE.TXT","w")
	if probe_file <> 0 then
		Fwrite_Fut("G3X_CBASIC_PROBE_OK\n",20,1,probe_file)
		Fclose_Fut(probe_file)
	end if
end sub
```

### Why these calls are evidence-supported

- `private sub Initialize()` is the documented Canon Basic callback. Source: [CHDK Wiki — Canon Basic](https://chdk.fandom.com/wiki/Canon_Basic), archived snapshot [`20240527012744`](https://web.archive.org/web/20240527012744id_/https://chdk.fandom.com/wiki/Canon_Basic), retrieved 2026-10-17.
- `System.Create()` is used directly by ranma's G3 X `GM1.10E` Canon Basic script. Source: [G3 X forum post 143433](https://chdk.setepontos.com/d/12600-g3-x-100c-fw-dump/18), 2020-05-11T11:03:54Z, retrieved 2026-10-17. This is evidence for the API family on G3 X, not proof of identical `GM1.10C` behavior.
- The `Fopen_Fut` → `Fwrite_Fut` → `Fclose_Fut` sequence and `A/` path are used by the CHDK Canon Basic Universal Dumper. Source: [CHDK Wiki — Dumper](https://chdk.fandom.com/wiki/Canon_Basic/Scripts/Dumper), archived snapshot [`20240724053956`](https://web.archive.org/web/20240724053956id_/https://chdk.fandom.com/wiki/Canon_Basic/Scripts/Dumper), retrieved 2026-10-17. Historical G3 X `1.00C` output included both `CBDUMPER.LOG` and `PRIMARY.BIN` (post 124672), establishing that Canon Basic file output worked on that G3 X revision, though the exact script bytes were not published.

No `GM1.10E` address, symbol, or memory assumption appears in Candidate P1.

### Exact behavior

1. Canon firmware invokes `Initialize()` only if script-disk recognition, file discovery, parsing, and the Playback/SET trigger succeed.
2. `System.Create()` requests standard DryOS event-procedure registration.
3. `Fopen_Fut("A/CBPROBE.TXT","w")` creates or truncates exactly one output file.
4. On a nonzero file handle, the script writes exactly 20 bytes:

   - ASCII: `G3X_CBASIC_PROBE_OK` followed by LF;
   - hexadecimal: `47 33 58 5f 43 42 41 53 49 43 5f 50 52 4f 42 45 5f 4f 4b 0a`.

5. It closes the handle and returns. It creates no status log and intentionally produces no LCD indication.

### Failure handling and limitations

- **Initialization failure:** Canon Basic provides no independently verified, safer reporting channel before procedure registration. If `System.Create()` is absent or faults on `GM1.10C`, execution may stop and no marker will appear. Candidate P1 does not call an unverified fallback, retry, UI routine, or hardware signal.
- **File-open failure:** `Fopen_Fut` returning `0` skips both write and close. The script returns without dereferencing an invalid handle and without attempting any alternative file or device operation.
- **Write failure:** the historical scripts do not establish a reliable return-value contract for `Fwrite_Fut`; Candidate P1 therefore closes the valid handle without branching on an unverified status convention. A missing, empty, truncated, or byte-mismatched marker is a failure result.
- **Diagnostic limit:** absence of `CBPROBE.TXT` cannot by itself distinguish script-disk rejection, trigger failure, parse failure, `System.Create()` failure, or SD write failure. Presence of the exact marker proves all of those stages succeeded sufficiently for this path.
- **Overwrite behavior:** mode `w` truncates an existing `CBPROBE.TXT`. The preflight procedure must confirm that no file by that name needs preservation.

### Static validation results

Validated locally on 2026-10-17 without executing Canon Basic:

| Check | Result |
|---|---|
| File type / encoding | `ASCII text`; no byte above `0x7f` |
| Size / lines | 303 bytes / 13 lines |
| SHA-256 | `ffea8a5aa7a5d17e9fc0191c1552b77cc45ae0cdb9dfe7b90b7c908034191ea5` |
| Marker length | Declared 20; decoded byte length 20 |
| Marker bytes | `4733585f4342415349435f50524f42455f4f4b0a` |
| Callable surface | `System.Create`, `Fopen_Fut`, `Fwrite_Fut`, `Fclose_Fut`, `Initialize` only |
| Forbidden-call scan | No `memcmp`, `strcmp`, peek/poke, allocation, UI/LCD, event-procedure-by-name, task creation, delete/remove/rename, hex address, firmware-dump name, or pointer dereference |
| Structural review | One `Initialize` block; one balanced `if`/`end if`; one closing `end sub` |
| Original dumper integrity | `firmware/tools/extend.m` remains SHA-256 `3ca970ba22c2e9b50cf84bfc1f63074c84b01808129e0f1fbf6af25e4b362da5` |

There is no offline Canon Basic parser in the reviewed repository, so syntax validation is lexical and comparative rather than executable. Each construct is copied from the documented syntax surface used by the cited scripts.

### Static safety review

Candidate P1 contains:

- no numeric address;
- no ROM, RAM, flash, NVRAM, register, LED, lens, sensor, task, or UI access;
- no read from camera memory;
- no firmware or boot-sector write;
- no loop, recursion, wait, retry, or persistent task;
- one bounded 20-byte SD-file write after a successful open.

The remaining risks are Canon Basic interpreter/event-procedure behavior and ordinary filesystem corruption risk from any on-camera write or power loss. Static review cannot establish physical-camera safety.

### Rollback to the pre-probe SD contents

This is a review procedure only; it was not performed in this session.

1. Before any approved preparation, copy the current on-card `extend.m` to a host backup and record its byte count and SHA-256. The expected Universal Dumper hash is `3ca970ba22c2e9b50cf84bfc1f63074c84b01808129e0f1fbf6af25e4b362da5`.
2. Confirm `A/CBPROBE.TXT` does not already contain user data. If it exists, back it up rather than allowing mode `w` to destroy it.
3. For the test only, copy Candidate P1 to the card root under the required name `extend.m`; do not alter `script.req`, the MBR, or the VBR.
4. After the single attempt and normal camera shutdown, copy any `CBPROBE.TXT` to the evidence location, then remove it from the card.
5. Restore the backed-up original `extend.m` byte-for-byte (or copy repository `firmware/tools/extend.m`) and verify SHA-256 `3ca970ba22c2e9b50cf84bfc1f63074c84b01808129e0f1fbf6af25e4b362da5` on the card.
6. Reverify `script.req` and the VBR marker against their pre-test hashes/readback. Because the probe does not alter either, any difference is unexpected: stop and preserve the card for review.
7. Eject/unmount normally. Do not raw-write a boot sector as part of this rollback. Restoring a pre-`SCRIPT` sector, if ever desired, is a separate destructive operation requiring its own approval and verified sector backup.

The file-level rollback restores the SD contents to the state immediately before Candidate P1 preparation: original dumper as `extend.m`, no probe marker, and unchanged script-disk metadata.
