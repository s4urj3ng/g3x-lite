# PORT-4A — External DIGIC 6 interrupt-controller documentation review

Date/retrieval date: **2026-10-25 (Asia/Seoul)**. Researcher: Codex.
Workspace: `/Users/avp/Project/g3x-lite`. Local HEAD at review start: `4577fb6ae74057571da923b51f61fbe0724a1595`; pre-existing dirty/untracked work is preserved.

**Final verdict: PARTIAL_DOCUMENTATION_ONLY.**

Public Magic Lantern documentation explicitly identifies `0xD4011000` as the DIGIC 6 current-interrupt-ID register. Generation-level documentation also supports ARMv7-R and conflicts with the prototype's Cortex-A9 annotation. **No applicable public documentation establishing the requested bank-write semantics or a G3 X interrupt-initialization/reset guarantee was located. Those hardware properties remain UNKNOWN.**

This verdict records partial documentation, not permission to execute a restart. Existing hardware readiness remains **NOT READY / STRICT NO-GO**.

## 1. Scope and evidence standard

Only public documentation, public source annotations used as documentation, and existing local audit documents were reviewed. No ROM was opened or disassembled. No call-tree/register-write enumeration, classifier-stopped investigation, firmware/code/test modification, build, test, emulator execution, MMIO probe, camera/SD-card operation, deployment, commit, push, or PR action occurred. Source comments were read, not changed. Outputs are this report and repository-required state/handoff entries.

Labels apply to individual propositions:

- **VERIFIED DOCUMENTATION:** a retrieved primary source explicitly states the proposition. This verifies the documentation and its scope, not every real-silicon implication of the statement.
- **INFERENCE:** an interpretation or applicability bridge beyond what the source explicitly establishes, including transfer between camera models.
- **UNKNOWN:** no sufficiently applicable supporting source was located, or a required guarantee is absent.

Sources were assessed for author/project provenance, version/date, named hardware, evidence type, and the exact guarantee stated. A developer's source comment is community reverse-engineering documentation, not a Canon register specification. Repeated/copied comments are not independent experiments. Emulator labels and successful emulation are not silicon validation.

The supplied forum URLs were searched and opened. Direct Magic Lantern forum access returned HTTP 403; CHDK direct retrieval timed out or was unavailable. The search service supplied indexed text from the original URLs. Forum quotations below are explicitly **indexed excerpts**, not claims that the entire live page or its attachments were inspected. Access failures are retrieval limitations, not evidence that a register definition does not exist.

## 2. Three strongest usable sources

These are ranked by relevance and retrievability for the narrow findings actually obtained, not as three proofs of restart safety. The supplied CHDK discussion and additional official/model-specific sources are assessed in §3.

### S1 — Magic Lantern Hardware Guide: generation architecture

- Original URL: [Hardware Guide, dev branch](https://github.com/reticulatedpines/magiclantern_simplified/blob/dev/developer_guide/02_00_hardware.md).
- Reviewed version: [commit-pinned file, lines 22–32](https://github.com/reticulatedpines/magiclantern_simplified/blob/142472e95054d73640f50789ac0fd66325499d82/developer_guide/02_00_hardware.md#L22-L32).
- Repository snapshot commit: `142472e95054d73640f50789ac0fd66325499d82`; commit timestamp reported by GitHub: `2026-10-04T11:31:02Z`. This is the reviewed repository snapshot date, **not an established last-edit date for the guide**. File Git blob: `c33b1053da8b3af0e99d0213ee916ca2f98f92ee`.
- Retrieval: full text via GitHub connector, first at `dev`, then at the resolved commit; both returned the same blob.
- Exact supporting passages: **“D6 uses ARMv7-R.”** (line 26); **“They have ARM GIC”** (line 32, whose subject is **D78X**, not D6).
- Applicability: a community developer guide distinguishing DIGIC generations. It does not identify G3 X GM1.10C silicon stepping or provide a `0xD401xxxx` register map. Its surrounding text expressly warns that hardware knowledge is incomplete and may contain errors.
- What it proves: **VERIFIED DOCUMENTATION** for the generation/profile distinction. Using it to predict all G3 X hardware behavior is **INFERENCE**. It supplies no bank-write/reset guarantee.

### S2 — Magic Lantern EOS M2 discussion: explicit DIGIC 6 ID-register note

- Original URL: [ML on EOS-M2, page 2](https://www.magiclantern.fm/forum/index.php?topic=15895.25).
- Version/date: indexed original-page excerpt retrieved 2026-10-25. The thread start is displayed as **2015-09-22**; the exact author, post date, last edit, and immutable revision of the particular quoted paragraph were **not reliably established**. The thread start must not be used as the paragraph's publication date.
- Exact supporting passage, from its quoted `CURRENT_ISR` documentation: **“on DIGIC 6, interrupt ID is MEM(0xD4011000)”**.
- Applicability: an explicit DIGIC 6 aside inside an EOS M2/DIGIC 5 emulation tutorial. The worked EOS M2 IRQ example uses the older `0xC0201004` interface and a shifted ID. That worked example is not a DIGIC 6 hardware test.
- What it proves: **VERIFIED DOCUMENTATION**, with the indexed-excerpt retrieval limitation, that ML documents the D6 ID-read location. It does not establish read side effects, write meanings, hardware reset behavior, or G3 X equivalence. Its older-generation enable/re-arm explanation cannot be transferred to `0xD4011010` merely because the offsets resemble one another.

### S3 — Pinned Magic Lantern 80D source annotation: corroborating model scope

- Original/reviewed URL: [80D.103/stubs.S, lines 40–44](https://github.com/reticulatedpines/magiclantern_simplified/blob/142472e95054d73640f50789ac0fd66325499d82/platform/80D.103/stubs.S#L40-L44).
- Version/date: the same commit snapshot/date as S1; file Git blob `fd21eedb9ad45b7da6092fbc588e43007318856b`. The comment's original observation date is not established by the snapshot date.
- Exact supporting passage, immediately after `current_interrupt`: **“It's read from d4011000, this was consistent on 3 Digic 6 cams I checked.”**
- Applicability: the inspected annotation is in the **EOS 80D firmware 1.0.3** platform file. Public search also found the same wording in the 7D2.112 and 750D.110 platform files; this report does not count the duplicated wording as three independent observations or identify the writer's original three test cameras from it.
- What it proves: **VERIFIED DOCUMENTATION** of the developer's current-ID interpretation and claimed cross-camera consistency. It corroborates S2 outside the forum excerpt. It is not an independently reproduced physical observation, does not name G3 X, and supplies no enable/pending/active/reset contract.

## 3. Other primary references and their exact limits

### S4 — Supplied CHDK DIGIC 6 discussion

- Original URL: [chdk in the DIGIC6 world, supplied cursor /158](https://chdk.setepontos.com/d/11316-chdk-in-the-digic6-world/158).
- Version/date: indexed text retrieved 2026-10-25; the relevant displayed contribution is **srsa_4c, post #148, 2018-03-26 22:59** (forum-displayed time, timezone unspecified). The URL suffix must not be mistaken for this displayed post number. No immutable revision/edit history was retrieved.
- Exact applicability passage: **“using sx280 102b addresses”**. Exact limitation passage: **“Later cameras do more stuff in their avcore initialization routines”**.
- Content/evidence: the contributor describes codec-core reinitialization after FI2 boot on an **SX280 1.02B**, a task/event/IRQ dependency, and limitations when moving to other models. The viewed excerpt concerns the audio/video core and other MMIO ranges, not a definition of the requested `0xD401xxxx` registers. It supports caution about cross-model initialization assumptions; it is not a G3 X reset guarantee.
- Classification: **VERIFIED DOCUMENTATION** of that limited community report; G3 X applicability and the requested register semantics remain **UNKNOWN**. No linked patches, attachments, or suggested workaround were executed or adopted.

### S5 — Related CHDK model observation: Cortex-R4

- Original URL: [same discussion, related cursor /185](https://chdk.setepontos.com/d/11316-chdk-in-the-digic6-world/185).
- Version/date: indexed original-page text retrieved 2026-10-25, **reyalp, post #175, 2020-01-04 07:39** (forum-displayed time, timezone unspecified); no immutable edit revision retrieved.
- Exact passage: **“The result is 0x411fc143 = Cortex-R4, just like the main core.”**
- Applicability: a reported CPU-ID observation on the **SX730 firmware 1.00D Omar core**, with the writer comparing the main core. This is a firsthand report concerning another D6 model, not G3 X CPU-ID evidence or proof of its active-core topology. No commands or attached patches from the post were run.
- Classification: **VERIFIED DOCUMENTATION** of the report; transferring its exact CPU configuration to G3 X is **INFERENCE**. It does not describe the requested IRQ-reset semantics.

### S6 — Canon: G3 X product-to-generation identification

- Original URL: [Canon Latin America, PowerShot G3 X](https://www.cla.canon.com/en/p/powershot-g3-x), section “Canon DIGIC 6 Image Processor”.
- Version/date: live product page retrieved 2026-10-25; page publication/update date and immutable revision not stated in the retrieved page.
- Exact passage: **“The PowerShot G3 X camera is powered by”** … **“the DIGIC 6 Image Processor”**.
- Applicability: **PowerShot G3 X specifically**, without firmware/stepping distinction. Canon establishes the marketed processor generation, not an ARM core identity, interrupt-controller register map, or reset guarantee.
- Classification: **VERIFIED DOCUMENTATION** for G3 X → DIGIC 6. Combining that with S1 supplies a documented-generation argument for ARMv7-R, not a Canon CPU-ID measurement.

### S7 — Arm: processor/profile definitions

- Original URL: [Arm fundamentals: introduction to understanding Arm processors](https://developer.arm.com/community/arm-community-blogs/b/architectures-and-processors-blog/posts/arm-fundamentals-introduction-to-understanding-arm-processors), processor-family/architecture table.
- Version/date: page dated **2013-09-11**, retrieved 2026-10-25; no separate immutable revision number shown.
- Exact relevant table entries: **“Cortex-A | Armv7-A | Cortex-A5, Cortex-A8, Cortex-A9”** and **“Cortex-R | Armv7-R | Cortex-R4”**.
- Applicability: authoritative Arm profile classification. It does not identify which core Canon integrated into G3 X and cannot document Canon-specific MMIO/reset semantics.
- Classification: **VERIFIED DOCUMENTATION** for Cortex-A9 belonging to the A profile, distinct from the R-profile description in S1.

## 4. Register-by-register result

The local baseline is [PORT-3B §1](/Users/avp/Project/g3x-lite/docs/PORT3B_IRQ_REGISTER_SEMANTICS.md:19). Its ROM-access findings were read as existing evidence and were **not re-derived or extended**. The table below concerns **external documentation**, not whether an instruction occurs in the firmware.

| Register / proposition | External support found | Classification and exact applicability | What remains unresolved for G3 X |
|---|---|---|---|
| `0xD401xxxx` is the D6 interrupt-controller area | S2 explicitly names the D6 current-ID read; S3 annotates the same read in an 80D platform file. | **VERIFIED DOCUMENTATION** for the specific current-ID interface; **INFERENCE** for a complete block/register model. This is independent of the local G3 X audit lineage, but is not a vendor register map. | Block extent, implementation identity/stepping, routing and reset contract. A matching address alone cannot establish full model equivalence. |
| `0xD401000C` and bank `+0xC` | No applicable definition located in the reviewed public documentation. | **UNKNOWN**. Local write patterns do not establish externally documented semantics. | Which attribute is affected; write-one versus other behavior; enable/pending/active effects; completeness, ordering and device reassertion behavior. |
| `0xD401010C` | No applicable definition located. | **UNKNOWN**. Its arithmetic position near the bank layout does not establish its function. | Whether it is a global control, another bank, a reset-related register, or something else; reset value/side effects. |
| `0xD4011000` | Explicit current-interrupt-ID statement in S2; corroborating named-platform annotation in S3. | **VERIFIED DOCUMENTATION** at community D6 level. Direct applicability to G3 X is **INFERENCE**, compatible with the existing local audit. | Whether reads acknowledge/mask/clear state, nesting behavior, idle value, and all hardware side effects. Neither source specifies these. |
| `0xD4011010` | No applicable D6 definition located. S2's worked enable/re-arm discussion concerns the older `0xC0201010` interface. | External D6 semantics **UNKNOWN**; local enable/re-arm interpretation remains **INFERENCE**. | Enable versus completion/re-arm behavior; interaction with ID reads, banks and reset. Older-generation offset similarity is not a guarantee. |
| `0xD4011018` | No applicable definition located. | External semantics **UNKNOWN**; the local paired-disable interpretation remains **INFERENCE**. | Disable effect, pending/active retention, synchronization and reset guarantees. |
| `0xD4011200` | No applicable definition located. | **UNKNOWN**. Read-back or write-one usage in local code does not document global-enable/reset semantics. | Register meaning, side effects and whether any initialization write establishes a quiescent state. |

**Initialization/reset guarantee: UNKNOWN.** No retrieved source promises that the already documented initialization disables all deliverable lines, clears pending and active/in-service state, or prevents a peripheral from reasserting before its handler is registered. Identifying the ID register does not satisfy that safety precondition. No mitigation follows from the new references.

## 5. Answers to the research questions

1. **Independent evidence for the block?** Yes, partial community documentation: S2/S3 independently identify the D6 current-ID address. Calling the entire range a fully documented controller would exceed their scope.
2. **Independent meanings for all six requested locations?** Only the current-ID role of `0xD4011000` received explicit external support. The other requested locations and read/write side effects remain UNKNOWN; prior local interpretations remain inferences.
3. **Initialization or interrupt-reset guarantee?** None applicable was located. Preserve UNKNOWN rather than interpreting absence of documentation as either evidence of safety or proof of failure.
4. **G3 X applicability?** S6 identifies G3 X as D6. S1/S2 are generation-level statements; S3–S5 concern other named cameras. No retrieved source establishes G3 X GM1.10C controller equivalence or a stepping-specific guarantee. The EOS M2 worked example is D5; S1's GIC statement is D7/8/X. Neither can be substituted for a D6 register contract.
5. **Cortex-A9 comment consistency?** The [prototype header, line 6](/Users/avp/Project/g3x-lite/chdk-port/platform/g3x/sub/110c/boot_prototype.c:6) says `DIGIC 6 (Cortex-A9)`. **Yes: this annotation is inconsistent with the documented D6 ARMv7-R profile**, given Arm's A9 profile classification. The conflict is documentary evidence against that annotation, not a fresh G3 X CPU-ID measurement. An exact G3 X core/stepping and active-core topology are not newly verified here. No comment or code was patched.

## 6. Search coverage, provenance and stopping boundary

The bounded search covered the three supplied URLs, the guide's commit-pinned version, primary Magic Lantern documentation/annotations and CHDK discussion excerpts, plus Canon and Arm material for model/profile applicability. Searches used the full requested hexadecimal addresses and combinations with Canon, DIGIC 6, interrupt-controller and reset terms. Unrelated platforms sharing hexadecimal address strings were rejected. One public-repository search for the ID-read address located documentation comments; it was not an IRQ caller or register-write-site enumeration. No external repository was cloned and no downloaded script was run.

Public QEMU tutorials/changelogs surfaced, but no vetted, hardware-linked guarantee for the requested initialization was found there. The source selection therefore stops at documentation and reported observations; no emulator implementation was adopted as a silicon specification and no emulator behavior was tested. A source's presence in a “working” project does not establish the required G3 X state transition.

Retrieval qualifications:

- S1/S3: full text retrieved through the GitHub connector at an exact commit; Git blob IDs recorded. Their common project lineage is disclosed, not treated as independent physical experiments.
- S2/S4/S5: original-URL indexed excerpts only; direct page failures recorded above. Search-index relative “published/crawled” ages were not converted into precise source dates. Unknown passage date/edit revision stays unknown.
- S6/S7: original Canon/Arm pages were opened. Living-page retrieval does not establish a hardware-revision guarantee.
- Quoted passages are short exact excerpts; the rest of each assessment is paraphrase or explicitly marked inference. No attachments or proprietary firmware were fetched.

Local required inputs, read at review-start HEAD on 2026-10-25:

| Input | SHA-256 of reviewed file |
|---|---|
| [PORT-3A](/Users/avp/Project/g3x-lite/docs/PORT3A_RESTART_IRQ_AUDIT.md) | `04bae2ceb9629fdf0b3d8525e10294fb41e2f90a4256995f6633c87d9e5a6602` |
| [PORT-3B](/Users/avp/Project/g3x-lite/docs/PORT3B_IRQ_REGISTER_SEMANTICS.md) | `1af7d3e231454f3c5b23846ee5280a3077b1ad656db88bb1ff2ab2d8e46465b7` |
| [PORT-3C, revised](/Users/avp/Project/g3x-lite/docs/PORT3C_RESTART_READINESS_MATRIX.md) | `5f7961e98b637896b5f3f6d9b26e4fe7a3c63030a9d757022e6a21d81c35b9ec` |
| [Independent restart review](/Users/avp/Project/g3x-lite/docs/CODEX_INDEPENDENT_RESTART_REVIEW.md) | `e540bad864e0d6eb4ead1fb5398922d70568a1864cf5a86e07ba7580e4e8ba60` |

## 7. Recommended next action

**Stop the register-semantics investigation at UNKNOWN and have the owner review this documentation result.** The modest evidence improvement is current-ID documentation plus correction of the architecture assumption; the retained-IRQ blocker is not closed.

Reopen the semantics question only if a new applicable source is supplied: a controller specification or a versioned empirical report identifying the exact controller/model and demonstrating the relevant initialization guarantee. Evaluate that source's applicability before considering any further work. Do not substitute another generation's register meanings, a guessed bank function, an undocumented QEMU model, a mitigation, or either classifier-stopped enumeration. This report neither proposes nor authorizes a physical experiment or phase transition.

Exact next command, documentation only:

```sh
cat /Users/avp/Project/g3x-lite/docs/PORT4A_EXTERNAL_DIGIC6_IRQ_REFERENCES.md
```

**Final verdict: PARTIAL_DOCUMENTATION_ONLY. G3 X interrupt-reset semantics and warm-restart safety remain UNKNOWN.**
