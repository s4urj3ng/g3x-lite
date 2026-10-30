/*
 * G3X Lite -- UI-001A Minimal Static Native Menu Payload
 * Target: Canon PowerShot G3 X, Firmware GM1.10C (Platform ID 0x32A8)
 * CPU: ARMv7-R Cortex-R4 (Thumb-2 mode)
 *
 * Description:
 * Straight-line non-leaf AAPCS function that configures colors and text
 * for 3 pre-allocated LCDMsg handles (Title, Item 1, Item 2), then returns
 * sentinel 0x47335834 ("G3X4", decimal 1194547252) in r0.
 *
 * Calling Convention:
 * - Entry: r0 = h0 (Title handle, 0..19)
 *          r1 = h1 (Item 1 handle, 0..19)
 *          r2 = h2 (Item 2 handle, 0..19)
 * - Callee-saved: r4, r5, r6, lr saved on stack (16 bytes, maintains 8-byte SP alignment)
 * - Exit:  r0 = 0x47335834
 *
 * Visual Layout:
 * - Line 0 (h0): Color 2 (Green), "G3X Lite - Main Menu"
 * - Line 1 (h1): Color 1 (White), "> System Info"
 * - Line 2 (h2): Color 1 (White), "  Settings"
 *
 * Total Size: Exactly 156 bytes (aligned to 4-byte boundary).
 */

	.syntax unified
	.arch armv7-r
	.thumb

	.globl _start
	.type _start, %function

_start:
	push	{r4, r5, r6, lr}
	mov	r4, r0			/* r4 = handle 0 (Title) */
	mov	r5, r1			/* r5 = handle 1 (Item 1) */
	mov	r6, r2			/* r6 = handle 2 (Item 2) */

	/* --- Line 0: Title Header (Color 2 = Green) --- */
	mov	r0, r4
	movs	r1, #2			/* Color 2 = Green (HW verified) */
	movw	r3, #0x99B1		/* LCDMsg_ChangeColor_native (0xFC0C99B0 | 1) */
	movt	r3, #0xFC0C
	blx	r3

	mov	r0, r4
	adr	r1, str_header
	movw	r3, #0x973D		/* LCDMsg_SetStr_native (0xFC0C973C | 1) */
	movt	r3, #0xFC0C
	blx	r3

	/* --- Line 1: Item 1 (Color 1 = White) --- */
	mov	r0, r5
	movs	r1, #1			/* Color 1 = White (HW verified) */
	movw	r3, #0x99B1
	movt	r3, #0xFC0C
	blx	r3

	mov	r0, r5
	adr	r1, str_item1
	movw	r3, #0x973D
	movt	r3, #0xFC0C
	blx	r3

	/* --- Line 2: Item 2 (Color 1 = White) --- */
	mov	r0, r6
	movs	r1, #1			/* Color 1 = White (HW verified) */
	movw	r3, #0x99B1
	movt	r3, #0xFC0C
	blx	r3

	mov	r0, r6
	adr	r1, str_item2
	movw	r3, #0x973D
	movt	r3, #0xFC0C
	blx	r3

	/* --- Return Sentinel 0x47335834 ("G3X4", decimal 1194547252) --- */
	movw	r0, #0x5834
	movt	r0, #0x4733
	pop	{r4, r5, r6, pc}

	.align 2
str_header:
	.asciz "G3X Lite - Main Menu"

	.align 2
str_item1:
	.asciz "> System Info"

	.align 2
str_item2:
	.asciz "  Settings"

	.align 2
	.size _start, . - _start
