/*
 * G3X Lite -- BOOT-001B Minimal Native LCD Output Payload
 * Target: Canon PowerShot G3 X, Firmware GM1.10C (Platform ID 0x32A8)
 * CPU: ARMv7-R Cortex-R4 (Thumb-2 mode)
 *
 * Description:
 * Minimal AAPCS-compliant non-leaf function that invokes Canon's native
 * LCDMsg_SetStr_native routine (0xFC0C973D) to display a visually distinct
 * confirmation banner on the LCD, then returns magic sentinel 0x47335832
 * ("G3X2", decimal 1194547250) in r0.
 *
 * Calling Convention:
 * - Entry: r0 = msg (LCDMsg handle allocated by Stage 1 loader, 0..19)
 * - Callee-saved: r4 preserved on stack; lr saved and restored to pc
 * - Exit: r0 = 0x47335832
 *
 * Total Size: Exactly 52 bytes (aligned to 4-byte boundary).
 */

	.syntax unified
	.arch armv7-r
	.thumb

	.globl _start
	.type _start, %function

_start:
	push	{r4, lr}             /* Save r4 and return address (8 bytes, maintains 8-byte SP align) */
	mov	r4, r0               /* Preserve message handle (r0) in callee-saved r4 */

	/* Load native firmware function pointer 0xFC0C973D via movw/movt */
	movw	r2, #0x973D          /* Lower 16 bits = 0x973D */
	movt	r2, #0xFC0C          /* Upper 16 bits = 0xFC0C -> r2 = 0xFC0C973D (Thumb vector) */

	/* Set up arguments for LCDMsg_SetStr_native(handle, const char *str) */
	adr	r1, str_banner       /* r1 = PC-relative pointer to embedded banner string */
	mov	r0, r4               /* r0 = msg handle */

	/* Call Canon native firmware display routine */
	blx	r2                   /* Invokes sub_fc0c973c (copies string & posts UI redraw event) */

	/* Set up return value sentinel: 0x47335832 ("G3X2", decimal 1194547250) */
	movw	r0, #0x5832          /* Lower 16 bits = 0x5832 */
	movt	r0, #0x4733          /* Upper 16 bits = 0x4733 -> r0 = 0x47335832 */

	/* Restore registers and return to exec dispatcher */
	pop	{r4, pc}             /* Restores r4 and returns to loc_fc602464 */

	.align 2
str_banner:
	.asciz "BOOT-001B: NATIVE PASS"

	.align 2
	.size _start, . - _start
