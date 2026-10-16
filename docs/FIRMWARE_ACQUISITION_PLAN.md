# Firmware acquisition plan — `GM1.10C` (`0x32A8`) Canon Basic ROM dump preparation

Updated: 2026-10-16  
Phase: **0D (preparation only)**. Phase 1 has **not** started.  
Status: Physical target confirmed (`GM1.10C`, `0x32A8`); primary dumper source verified and reviewed line-by-line; **stopped at the owner-approval gate (Gates A2 & A3)**.  
Scope: No camera interaction, SD-card modification, firmware download, binary analysis, tool installation, or build has been performed.

Evidence IDs (`E0xx`/`C0xx`/`L0xx`) refer to `docs/RESEARCH_LOG.md`.

---

## 1. Confirmed physical camera target (`BLK-01` resolved)

From the owner-provided physical camera firmware diagnostic screen (**E037**):

| Field | Confirmed value | Project significance |
|---|---|---|
| Camera model | `Canon PowerShot G3 X` | Matches project target (**E003**). |
| Internal firmware build | **`GM1.10C`** | Target CHDK subdirectory name: `platform/g3x/sub/110c/`. |
| Public firmware version | **`1.1.0.0`** | Proves public `1.1.0.0` spans at least two internal builds: `GM1.10C` (owner device) and `GM1.10E` (`ranma`'s forum target, **E005**, **C011**). |
| Platform ID | **`0x32A8`** (`12968` decimal) | Direct value for `PLATFORMID = 12968` in `platform/g3x/makefile.inc`. Adjacent to DIGIC 6 peers SX710 HS (`0x32A6` / `12966`) and EOS M10 (`0x32A0` / `12960`). |
| Video / region indicator | `PAL D` | Recorded for hardware baseline context. |
| Camera serial number | *Intentionally omitted* | Never stored in Git or workspace documentation per `docs/SAFETY.md`. |

**Implication of `GM1.10C` vs `GM1.10E`:** even if the historical `g3x_110e.patch` (`GM1.10E`) is later recovered, no ROM address, stub, or task offset from `110E` or `100C` may be assumed valid for `GM1.10C` without verification against the owner's `GM1.10C` dump.

---

## 2. Historical G3 X Canon Basic dump mechanism & provenance

### 2.1 Primary-source provenance

All three primary components of the Canon Basic dumping workflow have been recovered from archived primary CHDK documentation:

1. **Card format & trigger specification** — Archived CHDK Wiki [`Canon_Basic`](https://web.archive.org/web/20240527012744id_/https://chdk.fandom.com/wiki/Canon_Basic) (`20240527012744`) and [`Canon_Basic/Card_Setup`](https://web.archive.org/web/20220129011254id_/https://chdk.fandom.com/wiki/Canon_Basic/Card_Setup) (`20220129011254`) (**E038**):
   - Card filesystem: **FAT16 or FAT32** (SD/SDHC ≤32 GB; SDXC cards default to `exFAT`, which does not use the FAT16/FAT32 boot-sector offset).
   - Partition boot sector signature: ASCII `"SCRIPT"` (6 bytes, no NUL terminator) at offset **`0x1F0` (`496` decimal)** of the **first sector of the FAT partition** (Volume Boot Record, e.g. `/dev/diskNs1` on macOS — **not** the MBR at `/dev/diskN`).
   - Request file in root directory: `script.req` containing the exact 17-byte ASCII string **`for DC_scriptdisk`** (works with or without a trailing newline; **contradicts** earlier search-engine summaries that claimed `script.req` is empty, **C010**).
   - Script file in root directory: `extend.m` containing the Canon Basic source text.
   - Trigger on camera with `FUNC./SET` button (including G3 X): power on in **Playback mode**, then press **`FUNC./SET`**.

2. **Dumper script source & 32 MiB `PRIMARY.BIN` requirement** — Archived CHDK Wiki [`Canon_Basic/Scripts/Dumper`](https://web.archive.org/web/20240724053956id_/https://chdk.fandom.com/wiki/Canon_Basic/Scripts/Dumper) (`20141220173812`, `20150905224847`, and `20240724053956`) (**E039**):
   - Both the **Universal Dumper** (Candidate A, 123 lines) and the **Improved Universal Dumper** (Candidate B, 166 lines) contain the explicit DIGIC 6 detection clause:
     ```basic
     if memcmp(0xFC020004,"gaonisoy",8) = 0 then
         startaddr = 0xFC000000
         os = "dry"
         romsize = 0x2000000
         exit sub
     end if
     ```
   - This **source-verifies** the 32 MiB requirement: `0x2000000` bytes = **`33,554,432` bytes (exact 32 MiB)** dumped starting at `0xFC000000` to `A/PRIMARY.BIN`, with status logged to `A/CBDUMPER.LOG`.

3. **Historical execution on G3 X** (**E025**, **E029**, **E034**, **E039**):
   - Ten days after the `2015-09-05` wiki snapshot (`20150905224847`), forum user `Nippey` dumped `G3 X 1.00C` on `2015-09-15` (post 124672) and reported the exact outputs of this script: `PRIMARY.BIN (32MB)` and `CBDUMPER.LOG` (**E029**).
   - In 2020 (`ranma`, post 143433, **E034**) and 2023 (`chengdulittlea`, post 149971, **E025**), two additional G3 X users executed Canon Basic scripts (`System.Create()`, `UI.CreatePublic()`, `LCDMsg_Create()`) on G3 X bodies (including `1.10E`).

### 2.2 Compatibility with `GM1.10C`

- **Verified**: G3 X is DIGIC 6 (**E003**), `1.00C` and `1.10E` execute Canon Basic scripts (**E029**, **E034**), and `ranma` reported main firmware start at `0xFC020000` on `1.10E`/`1.20A` (**E006**), where DryOS places `"gaonisoy"` at `+0x04` (`0xFC020004`).
- **Plausible (high confidence, unverified until run on `GM1.10C`)**: `GM1.10C` maps ROM at `0xFC000000` with `"gaonisoy"` at `0xFC020004` and supports the same Canon Basic interpreter and event procedures (`System.Create`, `Fopen_Fut`, `Fwrite_Fut`, `Fclose_Fut`).
- **Candidate A vs Candidate B on `GM1.10C`**:
  - **Candidate A (Universal Dumper, recommended primary choice)** is the direct lineage of the 2015 script proven on G3 X `1.00C` (**E029**, **E039**). Its `GetStart()` probes `0xFFC00004`, `0xFF810004`, `0xFF820004`, `0xFF000004`, `0xFF020004` before `0xFC020004`. On G3 X `1.00C`, those high addresses were readable (the `0xFFF20270` / `0xFDF20270` high ROM region is mapped on DIGIC 6 ports, **E016**) and did not fault.
  - **Candidate B (Improved Universal Dumper, fallback if Candidate A does not reach `0xFC020004`)** calls `foundaddr = CreateProxyOfEventProcedure("CreateTask")` first and only probes the address range matching `foundaddr`, avoiding dereferencing `0xFF......` addresses when `CreateTask` is at `0xFC......`.

### 2.3 Known failure modes & mitigations

| Failure mode | Cause | Evidence | Mitigation |
|---|---|---|---|
| **Silent no-op when pressing `FUNC./SET`** |1. `"SCRIPT"` written to MBR (`/dev/diskN`) instead of FAT partition boot sector (`/dev/diskNs1`).<br>2. Card formatted as `exFAT` (>32 GB SDXC).<br>3. `script.req` left empty instead of `"for DC_scriptdisk"`.<br>4. Hidden `.txt` extension (`extend.m.txt`). | **E038**, **C010** | Format ≤32 GB card in-camera (FAT32), write `"SCRIPT"` to `/dev/rdiskNs1` offset `496` while unmounted, verify readback, verify exact filenames and byte counts. |
| **Camera shuts down with `ASSERT` or displays `FAILED`** | Non-ASCII bytes (such as `U+00A0` non-breaking spaces present in the 2014/2015 MediaWiki HTML, **E040**) or syntax corruption in `extend.m`. | **E038**, **E040** | Use only the verified pure 7-bit ASCII source from §3.1/§3.2 and verify SHA-256 before unmounting the card. |
| **No status text visible on LCD during dump** | `LCDMsg_Create` / `LCDMsg_SetStr` may not render over the active playback buffer on all DryOS builds. | **E039** (Wiki note) | Expected and harmless. Do **not** pull the battery or turn off the camera immediately; wait at least 60–90 seconds after card LED activity stops, then inspect `CBDUMPER.LOG` on the computer. |
| **Card write error (`"file error"` in `CBDUMPER.LOG`)** | Insufficient free space (<32 MiB free) or locked card switch. | **E039** | Ensure SD card lock tab is unlocked and >100 MB is free. |
| **Power loss mid-dump** | Depleted battery during the ~15–45 second 32 MiB SD write. | `docs/SAFETY.md` | Because the dumper only **reads** ROM and **writes** to the SD card, a power loss only truncates `PRIMARY.BIN` on the SD card (it does not write to camera flash), but a full battery is mandatory to avoid SD filesystem corruption. |

---

## 3. Exact source code & line-by-line safety review

### 3.1 Candidate A — CHDK Wiki "Universal dumper" (Primary candidate)

- **Primary source URL**: <https://web.archive.org/web/20240724053956id_/https://chdk.fandom.com/wiki/Canon_Basic/Scripts/Dumper> (Section 1; DIGIC 6 logic identical to `20150905224847` snapshot predating the 2015 G3 X `1.00C` dump, **E039**)
- **Retrieval date**: 2026-10-16
- **Encoding**: Pure 7-bit ASCII (`non_ascii=[]`, **E040**)
- **Size (LF line endings, with trailing newline)**: `2,689` bytes, `123` lines
- **SHA-256 (LF, 2,689 bytes)**: `3ca970ba22c2e9b50cf84bfc1f63074c84b01808129e0f1fbf6af25e4b362da5`

```basic
' dump ROM to A/PRIMARY.BIN 
' log to A/CBDUMPER.LOG
 
DIM startaddr=0
DIM os="unk"
DIM lcdmsg=0
DIM msgstr=0
DIM romsize=0
 
' detect start address and OS
' order must be from highest to lowest, since accessing outside of ROM may trigger an exception
private sub GetStart()
	if memcmp(0xFFC00004,"gaonisoy",8) = 0 then
		startaddr = 0xFFC00000
		os = "dry"
		exit sub
	end if
	if memcmp(0xFFC00008,"Copyrigh",8) = 0 then
		startaddr = 0xFFC00000
		os = "vx"
		exit sub
	end if
	if memcmp(0xFF810004,"gaonisoy",8) = 0 then
		startaddr = 0xFF810000
		os = "dry"
		exit sub
	end if
	if memcmp(0xFF820004,"gaonisoy",8) = 0 then
		startaddr = 0xFF810000
		os = "dry"
		exit sub
	end if
	if memcmp(0xFF810008,"Copyrigh",8) = 0 then
		startaddr = 0xFF810000
		os = "vx"
		exit sub
	end if
	if memcmp(0xFF000004,"gaonisoy",8) = 0 then
		startaddr = 0xFF000000
		os = "dry"
		exit sub
	end if
	if memcmp(0xFF020004,"gaonisoy",8) = 0 then
		startaddr = 0xFF010000
		os = "dry"
		exit sub
	end if
	if memcmp(0xFC020004,"gaonisoy",8) = 0 then
		startaddr = 0xFC000000
		os = "dry"
		romsize = 0x2000000
		exit sub
	end if
	if memcmp(0xE0020004,"gaonisoy",8) = 0 then
		startaddr = 0xE0000000
		os = "dry"
		romsize = 0x2000000
		exit sub
	end if
end sub
 
private sub RegisterProcs()
	' Newest cams (Dryos rel 43 and later) only have System.Create()
	' on older dryos cams SystemEventInit is an alias for System.Create()
	' ExecuteEventProcedure does is not registered by default on vx, 
	' but calling an unregistered is not fatal
	if System.Create() = -1 then
		SystemEventInit()
	end if
	if ExecuteEventProcedure("UI_RegistDebugEventProc") = -1 then
		ExecuteEventProcedure("UI.CreatePublic")
	end if
end sub
 
private sub InitMsg()
	lcdmsg = ExecuteEventProcedure("LCDMsg_Create")
	msgstr = AllocateMemory(80)
	' truncate log
	msgfile = Fopen_Fut("A/CBDUMPER.LOG","w")
	if msgfile <> 0 then
		Fclose_Fut(msgfile)
	end if
end sub
 
private sub PutMsg(msg)
	if lcdmsg >= 0 then
		LCDMsg_SetStr(lcdmsg,msg)
	end if
	msgfile = Fopen_Fut("A/CBDUMPER.LOG","a")
	if msgfile <> 0 then
		Fwrite_Fut(msg,strlen(msg),1,msgfile)
		Fwrite_Fut("\n",1,1,msgfile)
		Fclose_Fut(msgfile)
	end if
end sub
 
private sub Initialize()
	RegisterProcs()
	InitMsg()
	PutMsg("Started")
 
	GetStart()
 
	if startaddr <> 0 then
		sprintf(msgstr,"%0X %s",startaddr,os)
		PutMsg(msgstr)
		if romsize = 0 then
			romsize = 0xFFFFFFFC - startaddr
		end if
		dumpfile = Fopen_Fut("A/PRIMARY.BIN","w")
		if dumpfile <> 0 then
			Fwrite_Fut(startaddr,romsize,1,dumpfile)
			Fclose_Fut(dumpfile)
			Wait(500)
			PutMsg("done")
		else
			PutMsg("file error")
		end if
	else
		PutMsg("not found!")
	end if
	FreeMemory(msgstr)
end sub
```

### 3.2 Candidate B — CHDK Wiki "Improved universal dumper" (Fallback candidate)

- **Primary source URL**: <https://web.archive.org/web/20240724053956id_/https://chdk.fandom.com/wiki/Canon_Basic/Scripts/Dumper> (Section 2, **E039**)
- **Retrieval date**: 2026-10-16
- **Encoding**: Pure 7-bit ASCII (`non_ascii=[]`, **E040**)
- **Size (LF line endings, with trailing newline)**: `3,820` bytes, `166` lines
- **SHA-256 (LF, 3,820 bytes)**: `d06ff2ba31c973e70daa33c026b62ec8ba1b9b6b36063d5dd793e3894e0d0491`
- **Difference from Candidate A**: Calls `foundaddr = CreateProxyOfEventProcedure("CreateTask")` / `DeleteProxyOfEventProcedure("CreateTask")` (lines 17–18) and gates each `memcmp` block on `if foundaddr > 0x...` so that on a `0xFC000000` camera where `CreateTask` is at `0xFC......`, it skips reading `0xFFC00004`, `0xFF810004`, and `0xFF000004`, and calls `LCDMsg_Create(10,10,"Started",2)` + `LCDMsg_ChangeColor(lcdmsg,2)` + `LCDMsg_SetStr(lcdmsg,msg,0)`.

### 3.3 Line-by-line safety audit (Candidate A)

| Lines | Code / Operation | Safety & Side-Effect Assessment |
|---|---|---|
| `1–3` | Comments (`' dump ROM to A/PRIMARY.BIN`, `' log to A/CBDUMPER.LOG`) | Non-executable comments. |
| `4–8` | `DIM startaddr=0`, `os="unk"`, `lcdmsg=0`, `msgstr=0`, `romsize=0` | Declares 5 script-local interpreter variables initialized to safe defaults (`0` / `"unk"`). |
| `12–60` | `private sub GetStart()` — sequential `memcmp(..., "gaonisoy" / "Copyrigh", 8)` checks | **Read-only memory comparisons.** `memcmp` only reads 8 bytes at each candidate ROM header address (`0xFFC00004`, `0xFFC00008`, `0xFF810004`, `0xFF820004`, `0xFF810008`, `0xFF000004`, `0xFF020004`, `0xFC020004`, `0xE0020004`). Performs **zero writes**. On DIGIC 6 (`0xFC020004` == `"gaonisoy"`), sets `startaddr = 0xFC000000`, `os = "dry"`, `romsize = 0x2000000` (32 MiB) and immediately executes `exit sub` (line 52), never touching `0xE0020004`. |
| `62–73` | `private sub RegisterProcs()` — `System.Create()` / `SystemEventInit()`, `UI_RegistDebugEventProc` / `UI.CreatePublic` | Standard Canon event-procedure table registration in RAM (also used by `ranma` on G3 X `110E` in post 143433, **E034**). Does not modify flash, NVRAM, or hardware registers. |
| `75–83` | `private sub InitMsg()` — `LCDMsg_Create`, `AllocateMemory(80)`, `Fopen_Fut("A/CBDUMPER.LOG","w")` + `Fclose_Fut` | Allocates an 80-byte RAM string buffer (`msgstr`, freed on line 122) and truncates/creates `A/CBDUMPER.LOG` on the SD card (`A/` is the DryOS SD card mount). |
| `85–95` | `private sub PutMsg(msg)` — `LCDMsg_SetStr`, `Fopen_Fut("A/CBDUMPER.LOG","a")`, `Fwrite_Fut`, `Fclose_Fut` | Appends status line + newline to `A/CBDUMPER.LOG` on the SD card and updates the optional on-screen message handle. |
| `97–103` | `private sub Initialize()` — calls `RegisterProcs()`, `InitMsg()`, `PutMsg("Started")`, `GetStart()` | Entry callback invoked by Canon Basic when triggered. Logs `"Started"` to `A/CBDUMPER.LOG` before probing ROM. |
| `104–109` | `if startaddr <> 0` → `sprintf(msgstr,"%0X %s",startaddr,os)` → `PutMsg(msgstr)` | Formats `"FC000000 dry"` (13 bytes including NUL, well inside the 80-byte `msgstr` buffer) and logs it to `A/CBDUMPER.LOG`. Because `romsize` was already set to `0x2000000` on line 51, line 108 is skipped. |
| `110–118` | `dumpfile = Fopen_Fut("A/PRIMARY.BIN","w")` → `Fwrite_Fut(startaddr,romsize,1,dumpfile)` → `Fclose_Fut(dumpfile)` → `Wait(500)` → `PutMsg("done")` | **Core read-only ROM dump operation.** Opens `A/PRIMARY.BIN` on the SD card for writing, reads `0x2000000` bytes (`33,554,432` bytes) from ROM address `0xFC000000`, writes them to the SD card file, closes the file handle, waits 500 ms, and logs `"done"` to `A/CBDUMPER.LOG`. |
| `119–123` | `else PutMsg("not found!") end if` → `FreeMemory(msgstr)` → `end sub` | Logs `"not found!"` if no signature matched, frees the 80-byte `msgstr` heap buffer, and returns cleanly to the Canon Basic interpreter. |

**Safety Audit Verdict**: **PASS (Read-Only with respect to camera ROM/RAM/NVRAM).** The script contains zero pointer dereference writes (`*addr = ...`), zero `Poke8`/`Poke16`/`Poke32` calls, zero GPIO writes, and zero flash/ROM erase or update event procedures. Its only persistent writes are to `A/CBDUMPER.LOG` and `A/PRIMARY.BIN` on the removable SD card.

---

## 4. Pre-execution checklist, validation & rollback plan (requires Owner Gate A3 approval first)

**DO NOT EXECUTE ANY STEP BELOW UNTIL THE OWNER GRANTS EXPLICIT GATE A2 AND GATE A3 APPROVAL.**

### 4.1 Hardware & battery preconditions

- [ ] **P1 — Target verification**: Confirm the physical camera is the owner's `Canon PowerShot G3 X` (`GM1.10C`, `0x32A8`).
- [ ] **P2 — Full battery**: Charge the `NB-10L` battery to **100%** prior to inserting the script card. Never attempt a card dump on a low battery.
- [ ] **P3 — Dedicated SD/SDHC card (≤32 GB)**: Select a dedicated, non-essential SD or SDHC card (**2 GB to 32 GB**). Do **not** use an SDXC (>32 GB) card formatted as `exFAT`. Back up any existing photos on the card first.
- [ ] **P4 — Format card in-camera first**: Format the card using the G3 X's native Setup menu (`Format...`) so the camera creates its standard MBR + FAT16/FAT32 partition layout. Ensure no `.FI2` or `DISKBOOT.BIN` file exists on the card.

### 4.2 Host SD-card preparation checklist (macOS Intel host, after Gate A3 approval)

1. **Identify the SD card partition device carefully**:
   - Run `diskutil list` before and after inserting the SD card.
   - Identify the **FAT16/FAT32 partition slice** `/dev/diskNs1` (e.g., `DOS_FAT_32 CANON_DC`).
   - **CRITICAL HAZARD**: Never target `/dev/diskN` (the whole-disk MBR at LBA 0, where offset `0x1BE`–`0x1FD` holds the partition table). The `"SCRIPT"` tag at offset `0x1F0` (`496`) belongs in the **partition boot sector** (`/dev/diskNs1` / `/dev/rdiskNs1`) (**E038**).
2. **Write `script.req` and `extend.m` to the mounted card root (`/Volumes/CANON_DC` or equivalent)**:
   - Write exact 17-byte `script.req` (`"for DC_scriptdisk"`, no newline needed, **E038**):
     ```sh
     printf 'for DC_scriptdisk' > /Volumes/CANON_DC/script.req
     ```
   - Write Candidate A (§3.1) to `/Volumes/CANON_DC/extend.m` using pure 7-bit ASCII LF and verify:
     ```sh
     wc -c /Volumes/CANON_DC/script.req /Volumes/CANON_DC/extend.m
     shasum -a 256 /Volumes/CANON_DC/script.req /Volumes/CANON_DC/extend.m
     ```
     Expected:
     - `script.req`: `17` bytes, SHA-256 `ef1fbfe9ac98f2fd2f88c2fdc8c6aa8472dc0dd2fafce7be3c3a8d89bd9c1733`
     - `extend.m` (Candidate A, LF): `2,689` bytes, SHA-256 `3ca970ba22c2e9b50cf84bfc1f63074c84b01808129e0f1fbf6af25e4b362da5`
3. **Back up the partition boot sector, write `"SCRIPT"` at offset `0x1F0` (`496`), and verify readback**:
   - Unmount (do not eject) the FAT partition:
     ```sh
     diskutil unmount /dev/diskNs1
     ```
   - Save a 512-byte backup of the partition boot sector to `private/` and confirm it ends with `55 aa` and contains `FAT16` or `FAT32`:
     ```sh
     mkdir -p private/card-backup
     sudo dd if=/dev/rdiskNs1 of=private/card-backup/vbr.bak bs=512 count=1
     xxd -s 0x36 -l 8 private/card-backup/vbr.bak
     xxd -s 0x1f0 -l 16 private/card-backup/vbr.bak
     ```
   - Write `"SCRIPT"` (6 bytes) at offset `496` (`0x1F0`) of `/dev/rdiskNs1` and verify readback:
     ```sh
     printf 'SCRIPT' | sudo dd of=/dev/rdiskNs1 bs=1 seek=496 count=6 conv=notrunc
     sudo dd if=/dev/rdiskNs1 bs=1 skip=496 count=6 2>/dev/null | xxd
     ```
     Expected readback: `00000000: 5343 5249 5054  SCRIPT`.
   - Eject the card cleanly: `diskutil eject /dev/diskN`.

### 4.3 On-camera execution & rollback expectations

1. Ensure the SD card write-protect tab is **unlocked** and insert the card into the G3 X.
2. Power the camera on in **Playback mode** (press the Playback button).
3. Press **`FUNC./SET`** once (**E038**).
4. **Expected behavior during execution**:
   - The camera controls will become unresponsive while the script runs (`~15–45` seconds for a 32 MiB write).
   - Text (`Started`, `FC000000 dry`, `done`) may or may not be visible on the LCD (**E039**).
   - Wait until any card-access indicator stops and at least **60–90 seconds** have elapsed.
5. **Power off and rollback**:
   - Press the power button to turn the camera off. (If the camera does not power off via the button after 2 minutes of zero card activity, open the battery door / remove the battery, then reinsert it.)
   - Remove the SD card. With a normal SD card (or after formatting/restoring `vbr.bak`), the camera returns 100% to stock behavior because **nothing on the camera was modified**.
   - Once the dump is copied and verified on the computer, restore `private/card-backup/vbr.bak` (or re-format the SD card in-camera) so the card is no longer a script disk.

### 4.4 Output validation & SHA-256 verification

Insert the SD card into the Mac and run:

1. **Preserve read-only copies under `private/firmware/g3x/110c/`** (ignored by `.gitignore`, **E036**):
   ```sh
   mkdir -p private/firmware/g3x/110c
   cp /Volumes/CANON_DC/CBDUMPER.LOG /Volumes/CANON_DC/PRIMARY.BIN private/firmware/g3x/110c/
   chmod a-w private/firmware/g3x/110c/CBDUMPER.LOG private/firmware/g3x/110c/PRIMARY.BIN
   ```
2. **Inspect `CBDUMPER.LOG`**:
   ```sh
   cat private/firmware/g3x/110c/CBDUMPER.LOG
   ```
   Expected 3 lines:
   ```text
   Started
   FC000000 dry
   done
   ```
3. **Verify exact byte size and SHA-256**:
   ```sh
   stat -f '%N: %z bytes' private/firmware/g3x/110c/PRIMARY.BIN private/firmware/g3x/110c/CBDUMPER.LOG
   shasum -a 256 private/firmware/g3x/110c/PRIMARY.BIN private/firmware/g3x/110c/CBDUMPER.LOG | tee private/firmware/g3x/110c/SHA256SUMS
   ```
   - Expected `PRIMARY.BIN` size from `romsize = 0x2000000`: **`33,554,432` bytes** (**E039**).
   - Optional high-assurance check: perform a second dump run onto the card and confirm that both runs produce the **identical SHA-256** (or document any differing offset range if a flash variable sector differs).

---

## 5. Unresolved risks & explicit owner approval gate

### Unresolved risks
1. **Unverified on `GM1.10C` specifically (`RISK-01`)**: While proven on G3 X `1.00C` (**E029**) and `1.10E` (`ranma` Canon Basic script, **E034**), Candidate A has not yet been executed on `GM1.10C`. If reading `0xFFC00004` triggers a data abort on `GM1.10C`, the camera will halt/shut down harmlessly and Candidate B (§3.2) should be used instead.
2. **Touchscreen / lever trigger fallback (`RISK-02`)**: CHDK `Canon_Basic` docs note that `FUNC./SET` starts `extend.m` in Playback mode on standard cameras, while some touchscreen models without a traditional `FUNC./SET` trigger via the zoom lever (**E038**). G3 X has a physical `SET` button, and `Nippey`/`ranma`/`chengdulittlea` ran Canon Basic scripts on G3 X, but if pressing `SET` in Playback mode does not create `CBDUMPER.LOG`, the zoom-lever fallback is documented in `Canon_Basic` (**E038**).
3. **macOS raw-disk operator error (`RISK-03`)**: Running `sudo dd` against the wrong `/dev/diskN` device or against the MBR (`/dev/diskN`) instead of the partition VBR (`/dev/diskNs1`) can corrupt a disk partition table. Always verify `diskutil list` and inspect `private/card-backup/vbr.bak` before writing.

### Explicit Owner Approval Checklist (STOP GATE)

Before any agent or owner action moves past Phase 0D preparation, the owner must explicitly reply to approve:

- [ ] **Approval A2 (Phase 1 Entry)**: Authorize transitioning from Phase 0D to Phase 1 once the `GM1.10C` dump is acquired.
- [ ] **Approval A3 (On-Camera Canon Basic Dump Execution)**: Authorize preparing the dedicated SD card with Candidate A (§3.1, SHA-256 `3ca970ba22c2e9b50cf84bfc1f63074c84b01808129e0f1fbf6af25e4b362da5`) and running it on the owner's `GM1.10C` camera per §4, **or** state that the owner will run §4 independently and supply the resulting `PRIMARY.BIN` + `CBDUMPER.LOG` in `private/firmware/g3x/110c/`.
