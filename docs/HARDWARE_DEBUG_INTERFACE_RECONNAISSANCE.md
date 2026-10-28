# G3X Lite — Hardware Debug Interface Reconnaissance

**Target**: Canon PowerShot G3 X (GM1.10C, Platform ID `0x32A8`, DIGIC 6, Model `EC385`)  
**Worker**: G10 (UART / Hardware Report Correction)  
**Coordinator**: Gemini Coordinator  
**Tech Lead**: ChatGPT  
**Date**: 2026-10-28  
**Status**: **`RESEARCH_COMPLETE / FOR_REVIEW`**  
**Safety Gate**: **`STRICT NO-GO FOR HARDWARE DEPLOYMENT`** (Phase 0 Read-Only Investigation)

---

## 1. Executive Summary & Objective

The objective of this reconnaissance is to determine whether there is a practical, safe, and verifiable debug or observation interface that could assist in diagnosing the CHDK port on the Canon PowerShot G3 X (`GM1.10C`).

### The Observability Bottleneck
In early-boot custom firmware development, execution occurs before DryOS kernel initialization, before display framebuffer composition, and before the SD card filesystem is mounted. If early execution hangs or crashes (e.g., during MPU reconfiguration, cache invalidation, or initial interrupt unmasking), the camera displays a silent black screen. This produces zero diagnostic feedback and cannot be distinguished from a failed SD boot sequence without dedicated observation methods.

### Four-Tier Analytical Framework
To prevent conflating software code existence with physical hardware availability, this reconnaissance evaluates debug interfaces across four distinct tiers:
1. **Tier 1 (ROM Routine Existence)**: Subroutines and strings present in the compiled firmware binary.
2. **Tier 2 (UART Controller Initialization)**: Whether early-boot code actively configures serial controller MMIO registers.
3. **Tier 3 (Physical PCB Routing)**: Whether the SoC serial lines are electrically routed to accessible copper test pads or connectors on the motherboard.
4. **Tier 4 (Interactive Debug Shell Availability)**: Whether the firmware monitors input, responds to commands (e.g., TIO monitor shell), or operates solely as a passive transmit-only debug trace.

---

## 2. Research Evidence by Domain

### 2.1 Canon G3 X Teardown Photographs & Service Documentation

#### Primary Sources
1. **Digi-Service Video Teardown**:
   - *Title*: "How to repair Canon camera PowerShot G3X - Broken zoom button"
   - *URL*: [YouTube Teardown Video](https://www.youtube.com/watch?v=AUZIYQFEuOBfXfIVv_UnjJc1whcXUMxTbCjD4EkTMfrAvxYTIKYkXTHbqPPIKIAJiFYhyOUO_WboQ3nyOkFWwx16uiOm8C1dIEptKyzwAJIv281GMqPZ4cTMKZ5-MakuGYRCF2AU)
   - *Retrieval Date*: 2026-10-28
   - *Evidence Established*: Demonstrates outer shell removal, perimeter screw mapping, weather-sealing gasket placement, and disconnection of delicate top-plate and tilting LCD FPC ribbon cables to expose the chassis frame.
2. **Motherboard Spare Parts Identification (`CM2-1170`)**:
   - *Part Number*: `CM2-1170-000` (Main PCB Assembly for Canon PowerShot G3 X)
   - *URL*: [eBay Commercial Parts Listings & High-Res Photography](https://www.ebay.co.uk/itm/134448556637)
   - *Retrieval Date*: 2026-10-28
   - *Evidence Established*: Confirms the physical form factor of the G3 X logic board, metal RF/EM shielding cans covering the DIGIC 6 SoC and DRAM, placement of Micro-B USB and Micro-HDMI connectors, and surface copper test point clusters.
3. **iFixit Sibling Teardown References**:
   - *Canon PowerShot G7X Motherboard Replacement*: [iFixit Guide 128373](https://www.ifixit.com/Guide/Canon+PowerShot+G7X+Motherboard+Replacement/128373) (Model PC2201, DIGIC 6 sibling).
   - *Canon PowerShot G1 X Mark II Disassembly*: [iFixit Guide 62076](https://www.ifixit.com/Guide/Canon+PowerShot+G1+X+Mark+II+Disassembly+Guide/62076).
   - *Retrieval Date*: 2026-10-28
   - *Evidence Established*: Illustrates component density and confirms that Canon compact G-series cameras omit populated debug headers in favor of planar surface test pads.
4. **Official Canon Service Manuals**:
   - *Status*: **NOT_FOUND (PUBLIC DOMAIN)**. Canon restricts component-level circuit schematics and PCB layout diagrams to authorized factory service facilities.

---

### 2.2 Sibling Platform Precedents (EOS M3, EOS M10, 80D)

#### Community Knowledge Base
1. **Magic Lantern Hardware Wiki — Camera Debug Connectors**:
   - *URL*: [Magic Lantern Hardware Wiki: Debug Connectors](https://wiki.magiclantern.fm/hardware:connectors)
   - *Retrieval Date*: 2026-10-28
   - *Sibling Evidence*: Catalogs connector types across DIGIC generations. Notes EOS M3 and EOS M10 (DIGIC 6 cameras running PowerShot-derived code) utilize `SUR 6` (JST SUR 0.8mm pitch 6-pin connector) or surface pads. Catalogs EOS 80D as `SUR 14` and 750D/760D as `FZC 8`.
2. **Magic Lantern Forum — Battery Grip Pins / UART & Voltage Specifications**:
   - *URL*: [Magic Lantern Forum: Debug Pinouts](https://www.magiclantern.fm/forum/index.php?topic=14732.0)
   - *Retrieval Date*: 2026-10-28
   - *Sibling Evidence*: Identifies voltage domains on sibling DSLRs/mirrorless bodies:
     - **ICU (DIGIC Core / Cortex-R4)**: Reported operating at **1.8V CMOS logic** on EOS M3/80D.
     - **MPU (Power Management / Front Panel)**: Reported operating at **3.3V CMOS logic**.
     - *Caution*: These voltage levels are sibling observations and have not been measured on the PowerShot G3 X mainboard.
3. **CHDK Wiki & Forum — DIGIC 6/7 Porting & Low-Level Shells**:
   - *URL*: [CHDK Fandom: Digic 6-7 Porting](https://chdk.fandom.com/wiki/Digic_6-7_Porting) & [CHDK Forum: EOS M3 Porting](https://chdk.setepontos.com/index.php?topic=12532.0)
   - *Retrieval Date*: 2026-10-28
   - *Sibling Evidence*:
     - **Baud Rate**: Sibling bootloaders (EOS M3) utilize 115200 baud, 8N1.
     - **TIO Monitor Shell**: On EOS M3, early boot serial monitor responded to `'#'` character with low-level memory dump/edit commands.
     - *Caution*: Whether the G3 X bootloader enables interactive RX input or responds to TIO commands remains an unverified hypothesis.
4. **JTAG / SWD Status on DIGIC 6**:
   - *Sibling Evidence*: Magic Lantern research (kitor, a1ex) established that JTAG boundary scan and debugging are disabled or eFused on production DIGIC 6 silicon in sibling cameras.

---

### 2.3 G3 X Tracked ROM Evidence for UART Infrastructure

Based exclusively on existing tracked repository documentation:
1. **RomStarter UART Initialization (`0xFC0004AE`)**:
   - Subroutine `0xFC0004BC: bl 0xFC003004` configures hardware serial registers before main firmware execution (`docs/CHDK_PORT1A_STARTUP_TRACE.md`).
   - Subroutine `0xFC0004C8: bl 0xFC000460` performs a factory loopback jig check (`docs/CHDK_PORT0D_BOOT_RECOVERY.md`).
   - If triggered, it outputs status strings (`"DISKBOOT.BIN is started.\r\n"`) via `0xFC0030B0`:
     ```text
     0xFC0005E8: adr r0, #0xc8   ; "DISKBOOT.BIN is started.\r\n"
     0xFC0005EA: bl  #0xfc0030b0  ; Transmit string to UART
     0xFC0005EE: blx r4          ; Branch to payload entry
     ```
2. **Kernel Terminal Driver (`0xFC05C7D4`)**:
   - DryOS kernel initializes the serial console via `termDriverInit` (`0xFC05C7D4`) during startup stage 4 (`docs/CHDK_PORT2B1_RESTART_PRECONDITIONS.md`).

---

## 3. Four-Tier Classification: Confirmed Facts vs. Hypotheses

### Tier 1 & Tier 2: Confirmed Facts (Tracked ROM & Documentation)
- **FACT 1 (Mainboard ID)**: The G3 X mainboard assembly is Canon part number `CM2-1170` / `CM2-1170-000` (verified via parts cataloging and commercial listings).
- **FACT 2 (Model Code)**: The G3 X internal model code is `EC385` (verified via ROM string `#RomStarter Ver1.00 for EC385` at `0xFC0004FC`).
- **FACT 3 (Bootloader Serial Routine Existence)**: GM1.10C ROM contains bootloader routines that initialize a serial interface (`0xFC003004`) and reference string `"DISKBOOT.BIN is started.\r\n"` (`0xFC0030B0`).
- **FACT 4 (Kernel Terminal Existence)**: DryOS includes serial console initialization routines (`termDriverInit` at `0xFC05C7D4`).
- **FACT 5 (Standard External Ports Non-Functional for Early Debug)**: External Micro-B USB, Micro-HDMI, and 3.5mm jacks do not provide early-boot serial output. USB and HDMI require late-stage task initialization.

### Tier 3 & Tier 4: Sibling Inferences & Unverified Hypotheses (NOT Established on G3 X)
- **HYPOTHESIS 1 (PCB Pad Routing - Tier 3)**: Whether the UART TX/RX pins of the DIGIC 6 SoC are routed to accessible surface copper test pads on `CM2-1170` is **UNKNOWN**. Sibling cameras possess test pads, but continuity to G3 X pads has not been probed.
- **HYPOTHESIS 2 (Operating Voltage)**: That G3 X ICU UART logic levels are strictly **1.8V CMOS** is a **SIBLING INFERENCE** from EOS M3 / EOS 80D. It has NOT been measured on physical G3 X hardware.
- **HYPOTHESIS 3 (Baud Rate & Framing)**: That G3 X bootloader serial operates at **115200 8N1** is a **SIBLING INFERENCE**; actual timing register divisor values in `0xFC003004` have not been verified.
- **HYPOTHESIS 4 (TIO Shell Availability - Tier 4)**: That the G3 X bootloader responds interactively to `'#'` or provides a monitor shell is **UNKNOWN / UNVERIFIED**. It may be compile-time disabled, loopback-gated, or transmit-only.
- **HYPOTHESIS 5 (JTAG Security Configuration)**: That hardware JTAG is permanently fused off on the G3 X SoC is a **SIBLING INFERENCE** based on community findings on other DIGIC 6 models.

---

## 4. Evaluated Diagnostic & Observation Methods

| Method | Operating Mechanism | Firmware Prerequisite | Risk Profile | Feasibility Verdict on G3 X |
|---|---|---|:---:|---|
| **Internal UART Serial Console** | Polled writes to UART TX register | Bootloader init at `0xFC003004` | **Moderate Risk** (Requires hardware disassembly and physical probing) | **THEORETICAL HIGH VALUE / BLOCKED**: Sibling evidence is strong, but PCB pad routing is UNKNOWN. Strictly blocked under Phase 0 NO-GO. |
| **RAM Boot Witness (Post-Reboot Readout)** | Writing sentinel words to fixed DRAM | Warm reboot persistence | **Low Risk** (Bounded DRAM writes; non-destructive) | **CURRENT BEST METHOD**: Prototyped in `witness_inspector_gm110c.m`. Non-invasive, but blind if hard hang requires battery pull. |
| **Canon Basic Display (`LCDMsg`)** | Calling `LCDMsg_SetStr_native` | Canon UI task initialization complete | **Low Risk** (Standard firmware API invocation) | **PROVEN POST-BOOT**: Verified in BOOT-001A/B; cannot observe pre-kernel boot stages. |
| **USB PTP Memory Inspection** | PTP vendor transactions via USB | DryOS USB task initialization complete | **Low Risk** (Standard communication protocol) | **POST-BOOT ONLY**: Available once DryOS kernel and USB tasks are running. |
| **Direct MMIO GPIO Blinking** | Poking GPIO base registers (`0xD20B0000`) | None (bare-metal register write) | **HIGH RISK / HAZARDOUS** | **REJECTED**: GPIO multiplexing controls motor coils and power rails; unverified writes risk physical hardware damage. |
| **Hardware JTAG / SWD** | Boundary scan via external debug probe | External debug interface enabled | **Extreme Risk** (Requires soldering directly to BGA/micropads) | **REJECTED**: Presumed fused/disabled in production DIGIC 6 silicon based on sibling research. |

---

## 5. Offline Feasibility vs. Hardware Requirements

### What CAN Be Established Completely Offline (Phase 0 Compliant)
1. **Disassembly Analysis of `0xFC003004`**: Inspecting UART initialization code to identify the exact UART MMIO controller base address and baud rate divisor registers.
2. **Analysis of Factory Jig Detection (`0xFC000460`)**: Determining whether the serial loopback test requires external RX-TX bridging or specific GPIO pin pulls.
3. **Disassembly Analysis of `termDriverInit` (`0xFC05C7D4`)**: Mapping kernel-level terminal I/O functions and baud configurations.
4. **External Visual Inspection**: Examining public high-resolution PCB photographs of `CM2-1170` to catalog test pad coordinates relative to the SoC shield.

### Strict Hardware Safety Mandate
- **Phase 0 STRICT NO-GO**: Physical disassembly, electrical probing, soldering, and wire attachment are **STRICTLY PROHIBITED**.
- **High-Voltage Hazard**: Camera flash subsystems contain a high-voltage xenon strobe capacitor storing approximately **330V DC**. Disassembly involves substantial electrical shock hazards and the potential to vaporize PCB traces or destroy the camera if bridged. Amateur capacitor discharge procedures are hazardous and strictly excluded from project documentation.
- **Optical & Mechanical Risks**: Opening the sealed weather-resistant body risks compromising gasket integrity, tearing fragile FPC ribbon cables, and misaligning the complex 25x optical zoom assembly.
- Any future hardware inspection requires explicit human authorization and formal Phase 1 transition approval.
