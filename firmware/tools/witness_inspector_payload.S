/*
 * G3X Lite -- PORT-1G.1 Canon Basic Witness Inspector Native Payload
 * Target: Canon PowerShot G3 X, Firmware GM1.10C (Platform ID 0x32A8)
 * CPU: ARMv7-R Cortex-R4 (Thumb-2 mode)
 *
 * Description:
 * Isolated, non-deployable AAPCS function that:
 * 1. Reads boot_witness_t from dedicated linker-resolved DRAM address (BOOT_WITNESS_ADDR).
 * 2. Validates magic (0x5749544E), version (0x00010001), and polynomial checksum.
 * 3. Evaluates structural stage transitions and freshness:
 *    - INVALID: Corrupted magic, version, checksum, or non-monotonic transition.
 *    - LOADER_REACHED: State == 0x01 (STAGE_LOADER).
 *    - CORE_REACHED: State == 0x03 (STAGE_LOADER | STAGE_CORE).
 *    - CONTINUATION_ATTEMPTED: State == 0x07 (STAGE_LOADER | STAGE_CORE | STAGE_CONTINUATION).
 *    - STALE_OR_FRESHNESS_UNKNOWN: Dynamic challenge mismatch.
 * 4. CRITICAL FRESHNESS & SEMANTIC INVARIANTS (PORT-1G.1):
 *    - A matching constant nonce (0x32A80001) is NEVER considered freshness proof.
 *    - Every complete record lacking an independently verified current-attempt
 *      challenge is visibly labeled FRESHNESS_UNVERIFIED in Yellow (Color 4).
 *    - Misleading success coloring (Green / Color 2) is STRICTLY PROHIBITED.
 *    - NEVER reports BOOT_SUCCESS or CONTINUATION_CONFIRMED.
 * 5. Updates caller-provided LCDMsg handles using native LCDMsg APIs.
 *
 * Calling Convention:
 * - Entry: r0 = h_title (LCDMsg handle for stage line, 0..19)
 *          r1 = h_status (LCDMsg handle for freshness/integrity line, 0..19)
 *          r2 = expected_nonce (per-attempt dynamic challenge nonce, or 0/constant)
 *          r3 = 0 (reserved)
 * - Callee-saved: r4-r8, lr preserved on stack (24 bytes, maintains 8-byte SP alignment)
 * - Exit: r0 = sentinel:
 *          0x57495401: LOADER_REACHED
 *          0x57495402: CORE_REACHED
 *          0x57495404: CONTINUATION_ATTEMPTED
 *          0x574954EE: INVALID / CORRUPTED
 *          0x574954FF: STALE_OR_FRESHNESS_UNKNOWN
 */

	.syntax unified
	.arch armv7-r
	.thumb

	.globl _start
	.type _start, %function

_start:
	/* Save callee-saved registers (24 bytes = 6 * 4, maintains 8-byte SP alignment) */
	push	{r4, r5, r6, r7, r8, lr}

	mov	r4, r0			/* r4 = h_title */
	mov	r5, r1			/* r5 = h_status */
	mov	r6, r2			/* r6 = expected_nonce */

	/* Load pointer to boot_witness in DRAM (resolved automatically during build) */
#ifndef BOOT_WITNESS_ADDR
#error "BOOT_WITNESS_ADDR must be defined via -DBOOT_WITNESS_ADDR=0x... from candidate ELF symbol"
#endif
	movw	r7, #:lower16:BOOT_WITNESS_ADDR
	movt	r7, #:upper16:BOOT_WITNESS_ADDR

	/* --- Step 1: Read and validate magic & version --- */
	ldr	r0, [r7, #0]		/* r0 = w->magic */
	movw	r1, #0x544E
	movt	r1, #0x5749		/* r1 = 0x5749544E ("WITN") */
	cmp	r0, r1
	bne	.Lstate_invalid

	ldr	r0, [r7, #4]		/* r0 = w->version */
	movw	r1, #0x0001
	movt	r1, #0x0001		/* r1 = 0x00010001 */
	cmp	r0, r1
	bne	.Lstate_invalid

	/* --- Step 2: Compute and verify polynomial checksum over 7 words --- */
	/* Checksum formula: c = 0x55AA55AA; for each w: c = (c * 31) ^ w */
	movw	r8, #0x55AA
	movt	r8, #0x55AA		/* r8 = 0x55AA55AA */

	movs	r2, #0			/* r2 = word index (0..6) */
.Lchecksum_loop:
	ldr	r0, [r7, r2, lsl #2]	/* r0 = w[r2] */
	/* r8 = (r8 * 31) ^ r0 */
	movs	r1, #31
	mul	r8, r8, r1
	eor	r8, r8, r0
	adds	r2, r2, #1
	cmp	r2, #7
	bne	.Lchecksum_loop

	/* Compare with stored checksum at offset 28 */
	ldr	r0, [r7, #28]		/* r0 = w->checksum */
	cmp	r8, r0
	bne	.Lstate_invalid

	/* --- Step 3: Check dynamic challenge / replay --- */
	/*
	 * PORT-1G.1 Freshness Invariant:
	 * Constant nonce 0x32A80001 is NEVER considered freshness proof.
	 * If caller provided a non-zero, non-constant expected_nonce, verify match.
	 * If expected_nonce is a dynamic challenge and doesn't match session_nonce -> STALE.
	 */
	cmp	r6, #0
	beq	.Lcheck_stages

	/* Check if expected_nonce is the fixed constant nonce */
	movw	r1, #0x0001
	movt	r1, #0x32A8		/* r1 = 0x32A80001 (constant nonce) */
	cmp	r6, r1
	beq	.Lcheck_stages		/* Constant nonce cannot verify freshness; proceed to stages */

	/* Caller provided a non-constant dynamic challenge: verify exact match */
	ldr	r0, [r7, #8]		/* r0 = w->session_nonce */
	cmp	r0, r6
	bne	.Lstate_stale

.Lcheck_stages:
	/* --- Step 4: Evaluate stage state --- */
	ldr	r0, [r7, #12]		/* r0 = w->stage_state */

	cmp	r0, #1			/* STAGE_LOADER */
	beq	.Lstate_loader

	cmp	r0, #3			/* STAGE_LOADER | STAGE_CORE */
	beq	.Lstate_core

	cmp	r0, #7			/* STAGE_LOADER | STAGE_CORE | STAGE_CONTINUATION */
	beq	.Lstate_continuation

	/* Any other state bitmask is an illegal or incomplete transition */
	b	.Lstate_invalid

/* --- Outcome: LOADER_REACHED --- */
.Lstate_loader:
	adr	r1, str_title_ldr
	adr	r2, str_fresh_unv
	movs	r6, #1			/* Title Color 1 = White */
	movs	r7, #4			/* Status Color 4 = Yellow (Freshness Unverified) */
	movw	r8, #0x5401
	movt	r8, #0x5749		/* 0x57495401 */
	b	.Lrender

/* --- Outcome: CORE_REACHED --- */
.Lstate_core:
	adr	r1, str_title_cor
	adr	r2, str_fresh_unv
	movs	r6, #1			/* Title Color 1 = White */
	movs	r7, #4			/* Status Color 4 = Yellow (Freshness Unverified) */
	movw	r8, #0x5402
	movt	r8, #0x5749		/* 0x57495402 */
	b	.Lrender

/* --- Outcome: CONTINUATION_ATTEMPTED --- */
.Lstate_continuation:
	/* Sanity check on core_entry_pc */
	ldr	r0, [r7, #20]		/* r0 = w->core_entry_pc */
	movw	r1, #0x89B5
	movt	r1, #0x0034		/* 0x003489B5 */
	cmp	r0, r1
	bne	.Lstate_invalid

	/* Sanity check on loader_sp (must be 8-byte aligned) */
	ldr	r0, [r7, #16]		/* r0 = w->loader_sp */
	tst	r0, #7
	bne	.Lstate_invalid

	/*
	 * PORT-1G.1:
	 * Labeled strictly as CONT_ATTEMPTED, never boot success or confirmed.
	 * Rendered in Color 4 (Yellow), NEVER Green (Color 2 removed).
	 * Status line explicitly displays FRESHNESS_UNVERIFIED.
	 */
	adr	r1, str_title_con
	adr	r2, str_fresh_unv
	movs	r6, #4			/* Title Color 4 = Yellow */
	movs	r7, #4			/* Status Color 4 = Yellow */
	movw	r8, #0x5404
	movt	r8, #0x5749		/* 0x57495404 */
	b	.Lrender

/* --- Outcome: STALE_OR_FRESHNESS_UNKNOWN --- */
.Lstate_stale:
	adr	r1, str_title_stl
	adr	r2, str_nonce_err
	movs	r6, #4			/* Color 4 = Yellow */
	movs	r7, #4			/* Color 4 = Yellow */
	movw	r8, #0x54FF
	movt	r8, #0x5749		/* 0x574954FF */
	b	.Lrender

/* --- Outcome: INVALID --- */
.Lstate_invalid:
	adr	r1, str_title_inv
	adr	r2, str_corrupt
	movs	r6, #3			/* Color 3 = Red */
	movs	r7, #3			/* Color 3 = Red */
	movw	r8, #0x54EE
	movt	r8, #0x5749		/* 0x574954EE */
	b	.Lrender

/* --- Rendering step --- */
.Lrender:
	/*
	 * Arguments for render:
	 * - r4 = h_title, r5 = h_status
	 * - r1 = title_str pointer
	 * - r2 = status_str pointer
	 * - r6 = title_color
	 * - r7 = status_color
	 * - r8 = return sentinel
	 * Preserve string pointers across first ROM call (push 8 bytes, maintains 8-byte SP alignment)
	 */
	push	{r1, r2}

	/* 1. Update Title Color */
	mov	r0, r4			/* h_title */
	mov	r1, r6			/* title_color */
	movw	r3, #0x99B1		/* LCDMsg_ChangeColor_native (0xFC0C99B1) */
	movt	r3, #0xFC0C
	blx	r3

	/* 2. Update Title String */
	mov	r0, r4			/* h_title */
	ldr	r1, [sp, #0]		/* title_str */
	movw	r3, #0x973D		/* LCDMsg_SetStr_native (0xFC0C973D) */
	movt	r3, #0xFC0C
	blx	r3

	/* 3. Update Status Color */
	mov	r0, r5			/* h_status */
	mov	r1, r7			/* status_color */
	movw	r3, #0x99B1		/* LCDMsg_ChangeColor_native */
	movt	r3, #0xFC0C
	blx	r3

	/* 4. Update Status String */
	mov	r0, r5			/* h_status */
	ldr	r1, [sp, #4]		/* status_str */
	movw	r3, #0x973D		/* LCDMsg_SetStr_native */
	movt	r3, #0xFC0C
	blx	r3

	pop	{r1, r2}
	mov	r0, r8			/* Return sentinel */
	pop	{r4, r5, r6, r7, r8, pc}

	.align 2
str_title_ldr:
	.asciz "LOADER_REACHED"
str_title_cor:
	.asciz "CORE_REACHED"
str_title_con:
	.asciz "CONT_ATTEMPTED"
str_title_stl:
	.asciz "STALE / REPLAY"
str_title_inv:
	.asciz "WITNESS_INVALID"

str_fresh_unv:
	.asciz "FRESHNESS_UNVERIFIED"
str_nonce_err:
	.asciz "NONCE_MISMATCH"
str_corrupt:
	.asciz "INVALID / CORRUPT"

	.align 2
	.size _start, . - _start
