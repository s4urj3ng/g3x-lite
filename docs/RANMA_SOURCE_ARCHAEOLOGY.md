# Ranma G3 X Source Archaeology & Public Artifact Report

**Worker**: G9 (Ranma Source Archaeology)  
**Coordinator**: Gemini Coordinator  
**Tech Lead**: ChatGPT  
**Date**: 2026-10-28  
**Status**: **`RESEARCH_COMPLETE / FOR_REVIEW`**  
**Safety Gate**: **`STRICT NO-GO FOR HARDWARE DEPLOYMENT`** (Phase 0 Read-Only Investigation)

---

## 1. Executive Summary & Objective

The objective of Worker G9 is to establish the definitive provenance, accessibility, and artifact inventory of historical CHDK porting work conducted by contributor `ranma` on the Canon PowerShot G3 X.

### Core Findings
1. **Source Patch Recovered and Authenticated**: The patch file `g3x_110e.patch` (336,714 bytes; CRLF/LF mixed unified diff; SVN base r5480) is **fully recovered, authenticated, and verified** locally with SHA-256 `55927968545338c190100db97661ed4843b74b480c199af3cb643c00ccf1ccba`.
2. **Historical Spreadsheets Recovered**: Two 2015 historical research spreadsheets (`g3xstubs_102b.xlsx` and `20151215_g3xstubs_102b.xlsx`) are preserved byte-for-byte in the repository and cataloged by Worker G7.
3. **Firmware Binary Artifacts Inaccessible & Excluded**: Forum attachments `g3x_110e_fw.zip` and `g3x_120a_fw.zip` remain unrecovered due to forum access controls (HTTP 403 `permission_denied`) and are not archived on Wayback Machine. In accordance with Phase 0 rules, no attempt was made to bypass authentication or acquire proprietary pre-compiled camera binaries.
4. **No Upstream CHDK Merge**: The G3 X port was never merged into the official CHDK SVN trunk or public Git mirrors (`01luna/CHDK`). Only preliminary `finsig_thumb2` signature logic (r4437, r4438, r4444 in Feb 2016) was committed upstream.

---

## 2. Provenance & Chronological Archaeology

### 2.1 The Anchor Discussion: Thread 12600
- **URL**: `https://chdk.setepontos.com/d/12600-g3-x-100c-fw-dump`
- **Topic Title**: "G3 X 1.00C FW Dump"
- **Creation Date**: 2015-09-15T07:38:39Z
- **API Endpoint**: `https://chdk.setepontos.com/api/discussions/12600`
- **Total Posts in Thread**: 25 posts spanning 2015 to 2020.

### 2.2 Ranma's Posting Record (7 Posts Total)
Public API enumeration (`https://chdk.setepontos.com/api/posts?filter[author]=ranma`) confirms that user `ranma` published exactly 7 posts on the entire forum, all localized within thread 12600:

| Post ID | Date (UTC) | Post # | Key Contents & Claims | Attached Artifacts |
| :---: | :---: | :---: | :--- | :--- |
| **143399** | 2020-05-04 | #16 | States acquisition of G3 X with firmware 1.10E; mentions working on port. | None |
| **143401** | 2020-05-04 | #17 | Discusses initial boot attempts and LED blinking. | None |
| **143433** | 2020-05-10 | #18 | Reports successful boot to CHDK splash screen on 1.10E. | None |
| **143436** | 2020-05-11 | #20 | Mentions keymap implementation and menu navigation working. | None |
| **143437** | 2020-05-11 | #21 | **Releases initial patch and test build for GM1.10E.** | `g3x_110e.patch` (328.82 KB)<br>`g3x_110e_fw.zip` (174.64 KB) |
| **143438** | 2020-05-12 | #22 | Follow-up notes on battery indicator and zoom lever handling. | None |
| **143439** | 2020-05-12 | #23 | **Releases test build for GM1.20A.** | `g3x_120a_fw.zip` (174.83 KB) |

---

## 3. Artifact Verification & Accessibility Status

| Artifact Name | Claimed Source / Location | SHA-256 Checksum | Accessibility Status | Provenance Evaluation |
| :--- | :--- | :--- | :---: | :--- |
| **`g3x_110e.patch`** | Forum Post 143437; local file | `55927968545338c190100db97661ed4843b74b480c199af3cb643c00ccf1ccba` | **VERIFIED ACCESSIBLE** | Authentic unified diff (SVN r5480 base, 9,277 lines). |
| **`20151215_g3xstubs_102b.xlsx`** | Owner provided (2015 research) | `0fcd9dbf2047699256ccffe4a25e6ae62e7228efb4694b09e333b339418c666c` | **VERIFIED ACCESSIBLE** | Authentic 2015 1.00C symbol audit workbook (310 records). |
| **`g3xstubs_102b.xlsx`** | Owner provided (2015 draft) | `5b2732e4376b8bb543237503fa6e5786d687286d26b937779188fbd592ad95c5` | **VERIFIED ACCESSIBLE** | Authentic 2015 preliminary draft workbook. |
| **`g3x_110e_fw.zip`** | Forum Post 143437 (UUID `dc9012be...`) | *(Unknown)* | **UNRECOVERED / NOT FOUND** | Forum HTTP 403; Wayback capture absent; excluded by Phase 0. |
| **`g3x_120a_fw.zip`** | Forum Post 143439 (UUID `5f78d11e...`) | *(Unknown)* | **UNRECOVERED / NOT FOUND** | Forum HTTP 403; Wayback capture absent; excluded by Phase 0. |
| **`g3x_100c` source tree** | Hypothetical 2015 repository | *(N/A)* | **DOES NOT EXIST** | Never published as a standalone tree; work was in Excel stubs. |

---

## 4. Public Mirror & Repository Search Results

An exhaustive audit of public repositories and mirrors yielded the following results:
1. **GitHub `01luna/CHDK` (Trunk Mirror)**:
   - Checked `platform/` tree: No `g3x` platform directory exists.
   - Checked commit logs: Only `tools/finsig_thumb2.c` changes for G3 X were found (r4437, r4438, r4444 committed by PhilMoz in February 2016).
2. **Assembla SVN Repository (`subversion.assembla.com/svn/chdk`)**:
   - Access restricted (HTTP 401 Unauthorized / HTTP 403 Forbidden). No public read-only anonymous mirror accessible.
3. **GitHub User Search (`ranma`)**:
   - Multiple public accounts named `ranma` exist, but none host CHDK forks, Canon firmware tools, or camera-related repositories.
4. **Wayback Machine CDX API**:
   - Legacy attachment query for `attach=16495`, `attach=16496`, and `attach=16497` on `chdk.setepontos.com/index.php` returned zero archived snapshots (`archived_snapshots: {}`).

---

## 5. Architectural Evaluation of `g3x_110e.patch`

Inspection of the authenticated patch file (`g3x_110e.patch`) reveals:
1. **Baseline**: Applied cleanly against CHDK SVN revision `r5480` (May 2020).
2. **Sub-platform Structure**: Created `platform/g3x/sub/110e/` containing `boot.c`, `filewrite.c`, `stubs_entry.S`, `stubs_entry_2.S`, and `stubs_min.S`.
3. **Hook Set**:
   - `hook_CreateTask`: Patched at runtime in firmware RAM (`0xBFE14A40` / `0xBFE14A3C` area).
   - `mykbd_task`: Substituted for `task_PhySw` (`0xFC1283AD`).
   - `init_file_modules_task`: Cloned 17-instruction stock task at `0xFC0BD071`, inserting `core_spytask_can_start()`.
   - `filewrite_task`: Intercepted for remote PTP shoot functionality.
4. **Limitation for GM1.10C**: While the structural pattern is highly instructive, the addresses in `g3x_110e.patch` are strictly valid for **GM1.10E**. As established by Worker G8, piecewise modular shifts exist between versions, making direct application to GM1.10C unsafe without independent verification.

---

## 6. Phase 0 Compliance & Strict Rules

- **Zero ROM Reads / Scans**: No proprietary firmware binaries were inspected during this archaeology.
- **Zero Binary Execution**: No downloaded or candidate scripts were executed.
- **No Access Control Bypasses**: No credentials, authentication tricks, or scraper exploits were used against the CHDK forum.
- **Clear Classification**: All claims are strictly distinguished between verified accessible source files and unrecovered forum attachments.
