/*
 * G3X Lite -- UI-001B-0 One-Shot Input Probe Native Payload
 * Target: Canon PowerShot G3 X, Firmware GM1.10C (Platform ID 0x32A8)
 * CPU: ARMv7-R Cortex-R4 (Thumb-2 mode)
 *
 * Description:
 * Straight-line non-leaf AAPCS function that:
 * 1. Pre-fills caller-owned result buffer with canaries and sentinels.
 * 2. Invokes ROM GetKbdState(dest) exactly once to sample physical switches.
 * 3. Checks two boundary canaries (not proof of all memory safety).
 * 4. Converts raw 32-bit hardware words into uppercase ASCII hexadecimal strings
 *    using a self-contained Thumb-2 converter (no external sprintf dependencies).
 * 5. Updates 3 pre-allocated LCDMsg handles (Title, Line 1, Line 2).
 * 6. Returns sentinel 0x47335835 ("G3X5", decimal 1194547253) in r0.
 *
 * Calling Convention:
 * - Entry: r0 = h_title (Line 0 handle, 0..19)
 *          r1 = h_line1 (Line 1 handle, 0..19)
 *          r2 = h_line2 (Line 2 handle, 0..19)
 *          r3 = result_buf (caller-owned 24-byte buffer in DRAM)
 * - Callee-saved: r4-r8, lr saved on stack (24 bytes, maintains 8-byte SP alignment)
 * - Exit:  r0 = 0x47335835
 *
 * Stack frame layout (64 bytes allocated):
 * SP+00 .. SP+31: Line 1 text buffer (32 bytes)
 * SP+32 .. SP+63: Line 2 text buffer (32 bytes)
 * Total SP allocation = 64 bytes (64 is a multiple of 8, so SP % 8 == 0 is preserved).
 *
 * AAPCS 8-byte stack alignment is strictly maintained at every BL/BLX call site.
 */

	.syntax unified
	.arch armv7-r
	.thumb

	.globl _start
	.type _start, %function

_start:
	/* Save callee-saved registers: 6 registers * 4 = 24 bytes (multiple of 8) */
	push	{r4, r5, r6, r7, r8, lr}

	/* Move input arguments to callee-saved registers */
	mov	r4, r0			/* r4 = h_title */
	mov	r5, r1			/* r5 = h_line1 */
	mov	r6, r2			/* r6 = h_line2 */
	mov	r7, r3			/* r7 = result_buf */

	/* Defensive null check on result_buf */
	cmp	r7, #0
	beq	.Lerr_null

	/* Allocate 64 bytes for local stack buffers (Line 1 at sp, Line 2 at sp+32) */
	sub	sp, sp, #64
	/* At this point, SP % 8 == 0 is guaranteed if entered with AAPCS alignment */

	/* --- Step 1: Pre-fill caller-owned result_buf with canaries and sentinels --- */
	/* result_buf[0] (offset 0): Canary 1 = "CAN1" (0x314E4143) */
	movw	r0, #0x4143
	movt	r0, #0x314E
	str	r0, [r7, #0]

	/* result_buf[1..3] (offsets 4, 8, 12): pre-fill dest[0..2] with 0xDEADBEEF */
	movw	r0, #0xBEEF
	movt	r0, #0xDEAD
	str	r0, [r7, #4]
	str	r0, [r7, #8]
	str	r0, [r7, #12]

	/* result_buf[4] (offset 16): Canary 2 = "CAN2" (0x324E4143) */
	movw	r0, #0x4143
	movt	r0, #0x324E
	str	r0, [r7, #16]

	/* --- Step 2: Call GetKbdState(result_buf + 4 bytes) --- */
	add	r0, r7, #4		/* r0 = dest buffer (points to offset 4) */
	movw	r3, #0xEF67		/* GetKbdState Thumb entry (0xFC08EF66 | 1) */
	movt	r3, #0xFC08
	blx	r3			/* SP % 8 == 0 verified at call boundary */

	/* --- Step 3: Check canaries in native code --- */
	/* r8 = 1 if canaries intact, 0 if corrupted */
	movs	r8, #1

	ldr	r0, [r7, #0]
	movw	r1, #0x4143
	movt	r1, #0x314E
	cmp	r0, r1
	it	ne
	movne	r8, #0

	ldr	r0, [r7, #16]
	movw	r1, #0x4143
	movt	r1, #0x324E
	cmp	r0, r1
	it	ne
	movne	r8, #0

	/* --- Step 4: Construct Line 1 string at SP+0: "K0: XXXXXXXX K1: YYYYYYYY" --- */
	mov	r1, sp			/* r1 = output pointer */
	/* Store "K0: " */
	movw	r0, #0x304B		/* 'K', '0' */
	strh	r0, [r1], #2
	movw	r0, #0x203A		/* ':', ' ' */
	strh	r0, [r1], #2

	/* Format dest[0] hex */
	ldr	r0, [r7, #4]
	bl	hex32_internal

	/* Store " K1: " */
	movs	r0, #' '
	strb	r0, [r1], #1
	/* r1 is SP+13 here: use bytes, never odd-address STRH. */
	movs	r0, #'K'
	strb	r0, [r1], #1
	movs	r0, #'1'
	strb	r0, [r1], #1
	movs	r0, #':'
	strb	r0, [r1], #1
	movs	r0, #' '
	strb	r0, [r1], #1

	/* Format dest[1] hex */
	ldr	r0, [r7, #8]
	bl	hex32_internal

	/* Null terminator */
	movs	r0, #0
	strb	r0, [r1]

	/* --- Step 5: Construct Line 2 string at SP+32: "K2: ZZZZZZZZ CAN: OK" --- */
	add	r1, sp, #32		/* r1 = Line 2 buffer pointer */
	/* Store "K2: " */
	movw	r0, #0x324B		/* 'K', '2' */
	strh	r0, [r1], #2
	movw	r0, #0x203A		/* ':', ' ' */
	strh	r0, [r1], #2

	/* Format dest[2] hex */
	ldr	r0, [r7, #12]
	bl	hex32_internal

	/* Store " CAN: " */
	movw	r0, #0x4320		/* ' ', 'C' */
	strh	r0, [r1], #2
	movw	r0, #0x4E41		/* 'A', 'N' */
	strh	r0, [r1], #2
	movw	r0, #0x203A		/* ':', ' ' */
	strh	r0, [r1], #2

	/* Store "OK" or "FAIL" based on r8 */
	cmp	r8, #1
	beq	.Lcan_ok
	/* Canary failed */
	movw	r0, #0x4146		/* 'F', 'A' */
	strh	r0, [r1], #2
	movw	r0, #0x4C49		/* 'I', 'L' */
	strh	r0, [r1], #2
	b	.Lcan_done

.Lcan_ok:
	movw	r0, #0x4B4F		/* 'O', 'K' */
	strh	r0, [r1], #2

.Lcan_done:
	movs	r0, #0
	strb	r0, [r1]

	/* --- Step 6: Render Line 0 (Title, Color 2 = Green) --- */
	mov	r0, r4			/* h_title */
	movs	r1, #2			/* Color 2 = Green */
	movw	r3, #0x99B1		/* LCDMsg_ChangeColor_native */
	movt	r3, #0xFC0C
	blx	r3

	mov	r0, r4			/* h_title */
	adr	r1, str_title
	movw	r3, #0x973D		/* LCDMsg_SetStr_native */
	movt	r3, #0xFC0C
	blx	r3

	/* --- Step 7: Render Line 1 (Color 1 = White) --- */
	mov	r0, r5			/* h_line1 */
	movs	r1, #1			/* Color 1 = White */
	movw	r3, #0x99B1
	movt	r3, #0xFC0C
	blx	r3

	mov	r0, r5			/* h_line1 */
	mov	r1, sp			/* SP+0 (Line 1 string) */
	movw	r3, #0x973D
	movt	r3, #0xFC0C
	blx	r3

	/* --- Step 8: Render Line 2 (Color 1 = White) --- */
	mov	r0, r6			/* h_line2 */
	movs	r1, #1			/* Color 1 = White */
	movw	r3, #0x99B1
	movt	r3, #0xFC0C
	blx	r3

	mov	r0, r6			/* h_line2 */
	add	r1, sp, #32		/* SP+32 (Line 2 string) */
	movw	r3, #0x973D
	movt	r3, #0xFC0C
	blx	r3

	/* Deallocate local stack buffer */
	add	sp, sp, #64

	/* --- Step 9: Return sentinel 0x47335835 ("G3X5") --- */
	movw	r0, #0x5835
	movt	r0, #0x4733
	pop	{r4, r5, r6, r7, r8, pc}

.Lerr_null:
	/* Return error sentinel 0xEEEE0001 if result_buf is NULL */
	movw	r0, #0x0001
	movt	r0, #0xEEEE
	pop	{r4, r5, r6, r7, r8, pc}

/*
 * hex32_internal:
 * Formats 32-bit value in r0 into 8 uppercase ASCII hex chars at [r1].
 * Advances r1 by 8.
 * Clobbers: r0, r2, r3
 */
hex32_internal:
	movs	r2, #8
.Lhex_loop:
	ror	r0, r0, #28		/* Rotate left by 4 bits */
	and	r3, r0, #0xF		/* Isolate lower nibble */
	cmp	r3, #10
	ite	lt
	addlt	r3, #'0'
	addge	r3, #('A' - 10)
	strb	r3, [r1], #1
	subs	r2, r2, #1
	bne	.Lhex_loop
	bx	lr

	.align 2
str_title:
	.asciz "UI-001B-0: KBD PROBE"

	.align 2
	.size _start, . - _start
