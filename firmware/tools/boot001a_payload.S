/*
 * G3X Lite -- BOOT-001A Minimal Native Execution Payload
 * Target: Canon PowerShot G3 X, Firmware GM1.10C (Platform ID 0x32A8)
 * CPU: ARMv7-R Cortex-R4 (Thumb-2 mode)
 *
 * Description:
 * Smallest possible AAPCS-compliant leaf function returning magic sentinel
 * 0x47335831 (ASCII "G3X1", decimal 1194547249).
 * Contains zero hardware calls, zero memory writes, zero PC-relative literal
 * pools, and requires zero stack operations.
 */

	.syntax unified
	.arch armv7-r
	.thumb

	.globl _start
	.type _start, %function

_start:
	movw	r0, #0x5831         /* Lower 16 bits = 0x5831 */
	movt	r0, #0x4733         /* Upper 16 bits = 0x4733 -> r0 = 0x47335831 */
	bx	lr                  /* Return to caller with r0 preserved */
	nop                         /* Alignment padding to 12 bytes */

	.size _start, . - _start
