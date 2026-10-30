/*
 * G3X Lite -- UI-001B-1 Bounded Physical Button Sampler Native Payload
 * Target: Canon PowerShot G3 X, Firmware GM1.10C (Platform ID 0x32A8)
 * CPU: ARMv7-R Cortex-R4 (Thumb-2 mode)
 *
 * Description:
 * Bounded synchronous sampling function that:
 * 1. Checks result_buf for NULL.
 * 2. Pre-fills caller-owned result buffer (32 bytes) with canaries and zeroed diffs.
 * 3. Executes an initial settling delay of 10 iterations of SleepTask(30) (~300 ms nominal)
 *    to allow the camera owner to physically release FUNC./SET after script trigger.
 * 4. Takes a baseline snapshot of keyboard state via GetKbdState(temp_buf) [0xFC08EF67].
 * 5. Executes a strictly bounded sampling loop of 50 iterations of SleepTask(30) (~1500 ms nominal)
 *    sampling GetKbdState and accumulating bitwise XOR differences (diff |= sample ^ baseline).
 * 6. Stores baseline and diff words into caller-owned result buffer.
 * 7. Validates boundary canaries CAN1 and CAN2.
 * 8. Formats 3 telemetry lines using strictly byte-safe stack stores (strb):
 *    - Line 0 (Green): "UI-001B-1: K0=XXXXXXXX"
 *    - Line 1 (White): "D0: YYYYYYYY D1: ZZZZZZZZ"
 *    - Line 2 (White): "D2: WWWWWWWW CAN: OK"
 * 9. Updates 3 pre-allocated LCDMsg handles (h_title, h_line1, h_line2).
 * 10. Returns sentinel 0x47335836 ("G3X6", decimal 1194547254) in r0.
 *
 * Calling Convention:
 * - Entry: r0 = h_title (Line 0 handle, 0..19)
 *          r1 = h_line1 (Line 1 handle, 0..19)
 *          r2 = h_line2 (Line 2 handle, 0..19)
 *          r3 = result_buf (caller-owned 32-byte DRAM buffer)
 * - Callee-saved: r4-r8, r10, r11, lr saved on stack (32 bytes, maintains 8-byte SP alignment)
 * - Exit:  r0 = 0x47335836
 *
 * Stack frame layout (128 bytes allocated via sub sp, sp, #128):
 * SP+00 .. SP+11: temp_buf[0..2] for GetKbdState (12 bytes)
 * SP+12 .. SP+15: canary_ok status (4 bytes)
 * SP+16 .. SP+19: baseline[0] (4 bytes)
 * SP+20 .. SP+23: baseline[1] (4 bytes)
 * SP+24 .. SP+27: baseline[2] (4 bytes)
 * SP+28 .. SP+31: diff[2] (4 bytes)
 * SP+32 .. SP+63: Line 0 text buffer (32 bytes)
 * SP+64 .. SP+95: Line 1 text buffer (32 bytes)
 * SP+96 .. SP+127: Line 2 text buffer (32 bytes)
 * Total SP allocation = 128 bytes (128 is a multiple of 8, so SP % 8 == 0 is preserved).
 *
 * AAPCS 8-byte stack alignment is strictly maintained at every BL/BLX call site.
 */

	.syntax unified
	.arch armv7-r
	.thumb

	.globl _start
	.type _start, %function

_start:
	/* Save callee-saved registers: 8 registers * 4 = 32 bytes (multiple of 8) */
	push	{r4, r5, r6, r7, r8, r10, r11, lr}

	/* Move input arguments to callee-saved registers */
	mov	r4, r0			/* r4 = h_title */
	mov	r5, r1			/* r5 = h_line1 */
	mov	r6, r2			/* r6 = h_line2 */
	mov	r7, r3			/* r7 = result_buf */

	/* Defensive null check on result_buf */
	cmp	r7, #0
	beq	.Lerr_null

	/* Allocate 128 bytes for stack buffers (SP % 8 == 0 maintained) */
	sub	sp, sp, #128

	/* --- Step 1: Pre-fill caller-owned result_buf (32 bytes) --- */
	/* result_buf[0] (offset 0): Canary 1 = "CAN1" (0x314E4143) */
	movw	r0, #0x4143
	movt	r0, #0x314E
	str	r0, [r7, #0]

	/* Clear result_buf[1..6] (offsets 4, 8, 12, 16, 20, 24) */
	movs	r0, #0
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

	/* --- Step 2: Settling Phase (10 iterations of SleepTask(30) ~300 ms nominal) --- */
	movs	r8, #10
.Lsettle_loop:
	movs	r0, #30			/* r0 = 30 ms */
	movw	r3, #0xBF84		/* SleepTask ARM thunk (0xFC31BF84, bit 0 clear) */
	movt	r3, #0xFC31
	blx	r3			/* Calls ARM thunk; switches Thumb->ARM->Thumb */
	subs	r8, r8, #1
	bne	.Lsettle_loop

	/* --- Step 3: Baseline Snapshot --- */
	mov	r0, sp			/* r0 = temp_buf at SP+0 */
	movw	r3, #0xEF67		/* GetKbdState Thumb entry (0xFC08EF66 | 1) */
	movt	r3, #0xFC08
	blx	r3

	/* Save baseline values to stack */
	ldr	r0, [sp, #0]		/* baseline[0] */
	str	r0, [sp, #16]
	str	r0, [r7, #4]		/* store in result_buf */

	ldr	r1, [sp, #4]		/* baseline[1] */
	str	r1, [sp, #20]
	str	r1, [r7, #8]		/* store in result_buf */

	ldr	r2, [sp, #8]		/* baseline[2] */
	str	r2, [sp, #24]
	str	r2, [r7, #12]		/* store in result_buf */

	/* Initialize cumulative XOR diffs to 0 */
	movs	r10, #0			/* diff0 = 0 */
	movs	r11, #0			/* diff1 = 0 */
	movs	r0, #0
	str	r0, [sp, #28]		/* diff2 = 0 */

	/* --- Step 4: Sampling Loop (50 iterations of SleepTask(30) ~1500 ms nominal) --- */
	movs	r8, #50
.Lsample_loop:
	/* Sample keyboard switches into temp_buf at SP+0 */
	mov	r0, sp
	movw	r3, #0xEF67		/* GetKbdState */
	movt	r3, #0xFC08
	blx	r3

	/* diff0 |= (sample0 ^ baseline0) */
	ldr	r0, [sp, #0]
	ldr	r1, [sp, #16]
	eor	r0, r0, r1
	orr	r10, r10, r0

	/* diff1 |= (sample1 ^ baseline1) */
	ldr	r0, [sp, #4]
	ldr	r1, [sp, #20]
	eor	r0, r0, r1
	orr	r11, r11, r0

	/* diff2 |= (sample2 ^ baseline2) */
	ldr	r0, [sp, #8]
	ldr	r1, [sp, #24]
	eor	r0, r0, r1
	ldr	r2, [sp, #28]
	orr	r2, r2, r0
	str	r2, [sp, #28]

	/* Yield to scheduler for 30 ms */
	movs	r0, #30
	movw	r3, #0xBF84		/* SleepTask thunk */
	movt	r3, #0xFC31
	blx	r3

	subs	r8, r8, #1
	bne	.Lsample_loop

	/* --- Step 5: Save cumulative diffs into caller-owned result_buf --- */
	str	r10, [r7, #16]		/* result_buf->diff[0] */
	str	r11, [r7, #20]		/* result_buf->diff[1] */
	ldr	r0, [sp, #28]
	str	r0, [r7, #24]		/* result_buf->diff[2] */

	/* --- Step 6: Validate Canaries --- */
	/* r8 = 1 if canaries intact, 0 if corrupted */
	movs	r8, #1

	ldr	r0, [r7, #0]
	movw	r1, #0x4143
	movt	r1, #0x314E		/* "CAN1" */
	cmp	r0, r1
	it	ne
	movne	r8, #0

	ldr	r0, [r7, #28]
	movw	r1, #0x4143
	movt	r1, #0x324E		/* "CAN2" */
	cmp	r0, r1
	it	ne
	movne	r8, #0

	/* Store canary status on stack */
	str	r8, [sp, #12]

	/* --- Step 7: Format Line 0 at SP+32: "UI-001B-1: K0=XXXXXXXX" --- */
	add	r1, sp, #32
	/* "UI-001B-1: K0=" (15 bytes) */
	movs	r0, #'U'
	strb	r0, [r1], #1
	movs	r0, #'I'
	strb	r0, [r1], #1
	movs	r0, #'-'
	strb	r0, [r1], #1
	movs	r0, #'0'
	strb	r0, [r1], #1
	movs	r0, #'0'
	strb	r0, [r1], #1
	movs	r0, #'1'
	strb	r0, [r1], #1
	movs	r0, #'B'
	strb	r0, [r1], #1
	movs	r0, #'-'
	strb	r0, [r1], #1
	movs	r0, #'1'
	strb	r0, [r1], #1
	movs	r0, #':'
	strb	r0, [r1], #1
	movs	r0, #' '
	strb	r0, [r1], #1
	movs	r0, #'K'
	strb	r0, [r1], #1
	movs	r0, #'0'
	strb	r0, [r1], #1
	movs	r0, #'='
	strb	r0, [r1], #1

	/* Format baseline[0] in hex (8 bytes) */
	ldr	r0, [sp, #16]
	bl	hex32_internal

	/* Null terminator */
	movs	r0, #0
	strb	r0, [r1]

	/* --- Step 8: Format Line 1 at SP+64: "D0: YYYYYYYY D1: ZZZZZZZZ" --- */
	add	r1, sp, #64
	/* "D0: " */
	movs	r0, #'D'
	strb	r0, [r1], #1
	movs	r0, #'0'
	strb	r0, [r1], #1
	movs	r0, #':'
	strb	r0, [r1], #1
	movs	r0, #' '
	strb	r0, [r1], #1

	/* Format diff0 (r10) */
	mov	r0, r10
	bl	hex32_internal

	/* " D1: " */
	movs	r0, #' '
	strb	r0, [r1], #1
	movs	r0, #'D'
	strb	r0, [r1], #1
	movs	r0, #'1'
	strb	r0, [r1], #1
	movs	r0, #':'
	strb	r0, [r1], #1
	movs	r0, #' '
	strb	r0, [r1], #1

	/* Format diff1 (r11) */
	mov	r0, r11
	bl	hex32_internal

	/* Null terminator */
	movs	r0, #0
	strb	r0, [r1]

	/* --- Step 9: Format Line 2 at SP+96: "D2: WWWWWWWW CAN: OK" --- */
	add	r1, sp, #96
	/* "D2: " */
	movs	r0, #'D'
	strb	r0, [r1], #1
	movs	r0, #'2'
	strb	r0, [r1], #1
	movs	r0, #':'
	strb	r0, [r1], #1
	movs	r0, #' '
	strb	r0, [r1], #1

	/* Format diff2 from stack */
	ldr	r0, [sp, #28]
	bl	hex32_internal

	/* " CAN: " */
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

	/* "OK" or "FAIL" based on canary status */
	ldr	r8, [sp, #12]
	cmp	r8, #1
	beq	.Lcan_ok

	/* Canary failed: store "FAIL" */
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
	/* Canary OK: store "OK" */
	movs	r0, #'O'
	strb	r0, [r1], #1
	movs	r0, #'K'
	strb	r0, [r1], #1

.Lcan_done:
	movs	r0, #0
	strb	r0, [r1]

	/* --- Step 10: Render Line 0 (Title/K0, Color 2 = Green) --- */
	mov	r0, r4			/* h_title */
	movs	r1, #2			/* Color 2 = Green */
	movw	r3, #0x99B1		/* LCDMsg_ChangeColor_native */
	movt	r3, #0xFC0C
	blx	r3

	mov	r0, r4			/* h_title */
	add	r1, sp, #32		/* SP+32 (Line 0 string) */
	movw	r3, #0x973D		/* LCDMsg_SetStr_native */
	movt	r3, #0xFC0C
	blx	r3

	/* --- Step 11: Render Line 1 (Color 1 = White) --- */
	mov	r0, r5			/* h_line1 */
	movs	r1, #1			/* Color 1 = White */
	movw	r3, #0x99B1
	movt	r3, #0xFC0C
	blx	r3

	mov	r0, r5			/* h_line1 */
	add	r1, sp, #64		/* SP+64 (Line 1 string) */
	movw	r3, #0x973D
	movt	r3, #0xFC0C
	blx	r3

	/* --- Step 12: Render Line 2 (Color 1 = White) --- */
	mov	r0, r6			/* h_line2 */
	movs	r1, #1			/* Color 1 = White */
	movw	r3, #0x99B1
	movt	r3, #0xFC0C
	blx	r3

	mov	r0, r6			/* h_line2 */
	add	r1, sp, #96		/* SP+96 (Line 2 string) */
	movw	r3, #0x973D
	movt	r3, #0xFC0C
	blx	r3

	/* Deallocate local stack buffer */
	add	sp, sp, #128

	/* --- Step 13: Return sentinel 0x47335836 ("G3X6", 1194547254) --- */
	movw	r0, #0x5836
	movt	r0, #0x4733
	pop	{r4, r5, r6, r7, r8, r10, r11, pc}

.Lerr_null:
	/* Return error sentinel 0xEEEE0001 if result_buf is NULL */
	movw	r0, #0x0001
	movt	r0, #0xEEEE
	pop	{r4, r5, r6, r7, r8, r10, r11, pc}

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
	.size _start, . - _start
