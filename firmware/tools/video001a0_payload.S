/*
 * G3X Lite -- VIDEO-001A-0 Read-Only Diagnostic Probe Native Payload
 * Target: Canon PowerShot G3 X, Firmware GM1.10C (Platform ID 0x32A8)
 * CPU: ARMv7-R Cortex-R4 (Thumb-2 mode)
 *
 * Description:
 * Straight-line non-leaf AAPCS function that:
 * 1. Pre-fills caller-owned result buffer (32 bytes) with canaries and sentinels.
 * 2. Reads 4 MovieRecorder RAM locations:
 *    - 0x0000C0C8: mr_rec_state
 *    - 0x0000C274: mr_max_frames
 *    - 0x0000C278: mr_cur_frames
 *    - 0x0000C0E4: mr_warn_sec
 * 3. Verifies boundary canaries (CAN1 at offset 0, CAN2 at offset 28).
 * 4. Converts raw 32-bit values into uppercase ASCII hexadecimal strings
 *    using a self-contained Thumb-2 converter (no external sprintf dependencies).
 * 5. Updates 3 pre-allocated LCDMsg handles (Title, Line 1, Line 2).
 * 6. Returns sentinel 0x47335837 ("G3X7", decimal 1194547255) in r0.
 *
 * Calling Convention:
 * - Entry: r0 = h_title (Line 0 handle, 0..19)
 *          r1 = h_line1 (Line 1 handle, 0..19)
 *          r2 = h_line2 (Line 2 handle, 0..19)
 *          r3 = result_buf (caller-owned 32-byte buffer in DRAM)
 * - Callee-saved: r4-r8, lr saved on stack (24 bytes)
 * - Stack frame: 96 bytes allocated for Line 1 and Line 2 text formatting buffers.
 *   Total SP displacement = 24 + 96 = 120 bytes (120 % 8 == 0).
 * - Exit:  r0 = 0x47335837
 *
 * Safety Invariants:
 * - Read-only with respect to camera RAM and firmware globals.
 * - Stores strictly bounded to caller-owned result buffer [r7] and stack buffers [sp, r1].
 * - AAPCS 8-byte stack alignment strictly maintained at every BL/BLX call site.
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

	/* Allocate 96 bytes for local stack buffers (Line 1 at sp, Line 2 at sp+48) */
	sub	sp, sp, #96
	/* At this point, SP % 8 == 0 is guaranteed if entered with AAPCS alignment (24 + 96 = 120 B) */

	/* --- Step 1: Pre-fill caller-owned result_buf with canaries and sentinels --- */
	/* result_buf[0] (offset 0): Canary 1 = "CAN1" (0x314E4143) */
	movw	r0, #0x4143
	movt	r0, #0x314E
	str	r0, [r7, #0]

	/* result_buf[1..6] (offsets 4, 8, 12, 16, 20, 24): pre-fill with 0xDEADBEEF */
	movw	r0, #0xBEEF
	movt	r0, #0xDEAD
	str	r0, [r7, #4]
	str	r0, [r7, #8]
	str	r0, [r7, #12]
	str	r0, [r7, #16]
	str	r0, [r7, #20]
	str	r0, [r7, #24]

	/* result_buf[7] (offset 28): Canary 2 = "CAN2" (0x324E4143) */
	movw	r0, #0x4143
	movt	r0, #0x324E
	str	r0, [r7, #28]

	/* --- Step 2: Read MovieRecorder telemetry words (Read-Only) --- */
	/* 1. mr_rec_state from 0x0000C0C8 */
	movw	r2, #0xC0C8
	ldr	r0, [r2]
	str	r0, [r7, #4]

	/* 2. mr_max_frames from 0x0000C274 */
	movw	r2, #0xC274
	ldr	r0, [r2]
	str	r0, [r7, #8]

	/* 3. mr_cur_frames from 0x0000C278 */
	movw	r2, #0xC278
	ldr	r0, [r2]
	str	r0, [r7, #12]

	/* 4. mr_warn_sec from 0x0000C0E4 */
	movw	r2, #0xC0E4
	ldr	r0, [r2]
	str	r0, [r7, #16]

	/* Clear reserved words */
	movs	r0, #0
	str	r0, [r7, #20]
	str	r0, [r7, #24]

	/* --- Step 3: Check canaries in native code --- */
	/* r8 = 1 if canaries intact, 0 if corrupted */
	movs	r8, #1

	ldr	r0, [r7, #0]
	movw	r1, #0x4143
	movt	r1, #0x314E
	cmp	r0, r1
	it	ne
	movne	r8, #0

	ldr	r0, [r7, #28]
	movw	r1, #0x4143
	movt	r1, #0x324E
	cmp	r0, r1
	it	ne
	movne	r8, #0

	/* --- Step 4: Construct Line 1 string at SP+0: "MAX: XXXXXXXX CUR: YYYYYYYY" --- */
	mov	r1, sp			/* r1 = output pointer */
	/* Store "MAX: " */
	movs	r0, #'M'
	strb	r0, [r1], #1
	movs	r0, #'A'
	strb	r0, [r1], #1
	movs	r0, #'X'
	strb	r0, [r1], #1
	movs	r0, #':'
	strb	r0, [r1], #1
	movs	r0, #' '
	strb	r0, [r1], #1

	/* Format mr_max_frames hex (offset 8) */
	ldr	r0, [r7, #8]
	bl	hex32_internal

	/* Store " CUR: " */
	movs	r0, #' '
	strb	r0, [r1], #1
	movs	r0, #'C'
	strb	r0, [r1], #1
	movs	r0, #'U'
	strb	r0, [r1], #1
	movs	r0, #'R'
	strb	r0, [r1], #1
	movs	r0, #':'
	strb	r0, [r1], #1
	movs	r0, #' '
	strb	r0, [r1], #1

	/* Format mr_cur_frames hex (offset 12) */
	ldr	r0, [r7, #12]
	bl	hex32_internal

	/* Null terminator */
	movs	r0, #0
	strb	r0, [r1]

	/* --- Step 5: Construct Line 2 string at SP+48: "ST: XXXXXXXX W: YYYYYYYY CAN: OK" --- */
	add	r1, sp, #48		/* r1 = Line 2 buffer pointer */
	/* Store "ST: " */
	movs	r0, #'S'
	strb	r0, [r1], #1
	movs	r0, #'T'
	strb	r0, [r1], #1
	movs	r0, #':'
	strb	r0, [r1], #1
	movs	r0, #' '
	strb	r0, [r1], #1

	/* Format mr_rec_state hex (offset 4) */
	ldr	r0, [r7, #4]
	bl	hex32_internal

	/* Store " W: " */
	movs	r0, #' '
	strb	r0, [r1], #1
	movs	r0, #'W'
	strb	r0, [r1], #1
	movs	r0, #':'
	strb	r0, [r1], #1
	movs	r0, #' '
	strb	r0, [r1], #1

	/* Format mr_warn_sec hex (offset 16) */
	ldr	r0, [r7, #16]
	bl	hex32_internal

	/* Store " CAN: " */
	movs	r0, #' '
	strb	r0, [r1], #1
	movs	r0, #'C'
	strb	r0, [r1], #1
	movs	r0, #'A'
	strb	r0, [r1], #1
	movs	r0, #'N'
	strb	r0, [r1], #1
	movs	r0, #':'
	strb	r0, [r1], #1
	movs	r0, #' '
	strb	r0, [r1], #1

	/* Store "OK" or "FAIL" based on r8 */
	cmp	r8, #1
	beq	.Lcan_ok
	/* Canary failed */
	movs	r0, #'F'
	strb	r0, [r1], #1
	movs	r0, #'A'
	strb	r0, [r1], #1
	movs	r0, #'I'
	strb	r0, [r1], #1
	movs	r0, #'L'
	strb	r0, [r1], #1
	b	.Lcan_done

.Lcan_ok:
	movs	r0, #'O'
	strb	r0, [r1], #1
	movs	r0, #'K'
	strb	r0, [r1], #1

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
	add	r1, sp, #48		/* SP+48 (Line 2 string) */
	movw	r3, #0x973D
	movt	r3, #0xFC0C
	blx	r3

	/* Deallocate local stack buffer */
	add	sp, sp, #96

	/* --- Step 9: Return sentinel 0x47335837 ("G3X7") --- */
	movw	r0, #0x5837
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
	.asciz "VIDEO-001A-0: REC PROBE"

	.align 2
	.size _start, . - _start
