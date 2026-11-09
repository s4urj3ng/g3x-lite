' G3X Lite -- PORT-1G.1 Canon Basic RAM Witness Inspector Loader
' Target: Canon PowerShot G3 X, Firmware GM1.10C (Platform ID 0x32A8)
' Status: Isolated offline-reviewed non-deployable diagnostic prototype.
'         NOT APPROVED FOR HARDWARE EXECUTION.
'
' SCOPED DISPLAY LAYOUT (PORT-1G.1):
' - h_title  (x=60, y=140): Stage reached (Color dynamic, 1=White, 4=Yellow, 3=Red):
'     * "CONT_ATTEMPTED" (Yellow) - All 3 early boot stages reached.
'     * "CORE_REACHED"   (White)  - Handoff to core completed; continuation not reached.
'     * "LOADER_REACHED" (White)  - Loader executed core_copy; core not reached.
'     * "STALE / REPLAY" (Yellow) - Dynamic challenge mismatch.
'     * "WITNESS_INVALID"(Red)    - Corrupted checksum, bad magic/version.
' - h_status (x=60, y=180): Freshness & integrity (Color dynamic, 4=Yellow, 3=Red):
'     * "FRESHNESS_UNVERIFIED" (Yellow) - Freshness unverified across warm restart.
'     * "NONCE_MISMATCH"       (Yellow) - Dynamic challenge failed.
'     * "INVALID / CORRUPT"    (Red)    - Checksum/header failure.
'
' CRITICAL SEMANTIC INVARIANTS (PORT-1G.1):
' 1. This inspector NEVER outputs claims of complete boot success or confirmation.
' 2. Stage 3 represents CONTINUATION_ATTEMPTED.
' 3. Misleading success coloring (Green / Color 2) is strictly prohibited.
' 4. A matching constant nonce (0x32A80001) is NEVER considered freshness proof.
' 5. Every complete record lacking an independent challenge shows FRESHNESS_UNVERIFIED.
' 6. Continuation confirmation requires independent post-continuation evidence outside the witness.

DIM payload_size = 444
DIM expected_payload_size = 444
DIM expected_nonce = 0
DIM cache_clean_d = 0xfc127a85
DIM cache_inval_i = 0xfc127b2b
DIM h_title = 255
DIM h_status = 255

private sub check_compat()
	check_compat = 0
	if memcmp(0xfc020004, "gaonisoy", 8) <> 0 then
		exit sub
	end if
	if strcmp("EC385\n\r", 0xfc00052c) <> 0 then
		exit sub
	end if
	if strcmp("GM1.10C", 0xfc54e08d) <> 0 then
		exit sub
	end if
	check_compat = 1
end sub

private sub setup()
	System.Create()
	UI.CreatePublic()

	h_title = LCDMsg_Create()
	if h_title < 0 then
		h_title = 255
		exit sub
	end if
	if h_title > 19 then
		h_title = 255
		exit sub
	end if

	h_status = LCDMsg_Create()
	if h_status < 0 then
		LCDMsg_Delete(h_title)
		h_title = 255
		h_status = 255
		exit sub
	end if
	if h_status > 19 then
		LCDMsg_Delete(h_title)
		h_title = 255
		h_status = 255
		exit sub
	end if

	if h_title = h_status then
		LCDMsg_Delete(h_title)
		h_title = 255
		h_status = 255
		exit sub
	end if

	LCDMsg_Move(h_title, 60, 140)
	LCDMsg_Move(h_status, 60, 180)
	LCDMsg_ChangeColor(h_title, 1)
	LCDMsg_ChangeColor(h_status, 1)
	LCDMsg_SetStr(h_title, "PORT-1G: INIT")
	LCDMsg_SetStr(h_status, "STATUS: PENDING")
end sub

private sub run_inspector()
	run_inspector = 0
	buf = AllocateMemory(payload_size + 4)
	if buf = 0 then
		LCDMsg_SetStr(h_title, "PORT-1G: ERR_ALLOC")
		LCDMsg_SetStr(h_status, "ALLOCATION FAILED")
		exit sub
	end if

	fh = Fopen_Fut("A/WITNESS.BIN", "rb")
	if fh = 0 then
		LCDMsg_SetStr(h_title, "PORT-1G: ERR_OPEN")
		LCDMsg_SetStr(h_status, "WITNESS.BIN NOT FOUND")
		FreeMemory(buf)
		exit sub
	end if

	' Read up to payload_size + 1 to detect short, exact, or oversized payloads:
	read_sz = Fread_Fut(buf, 1, payload_size + 1, fh)
	cl = Fclose_Fut(fh)
	if read_sz <> payload_size then
		LCDMsg_SetStr(h_title, "PORT-1G: ERR_READ")
		LCDMsg_SetStr(h_status, "SIZE MISMATCH")
		FreeMemory(buf)
		exit sub
	end if
	if cl <> 0 then
		LCDMsg_SetStr(h_title, "PORT-1G: ERR_CLOSE")
		LCDMsg_SetStr(h_status, "CLOSE FAILED")
		FreeMemory(buf)
		exit sub
	end if

	' Synchronize L1 Harvard caches prior to executing loaded native code:
	' 0xFC127A85 performs DCCSW clean over entire L1 D-cache to PoC.
	' 0xFC127B2B performs ICIALLU/BPIALL invalidation and pipeline flush.
	ExecuteEventProcedure("exec", cache_clean_d, 0, 0, 0, 0, 0)
	ExecuteEventProcedure("exec", cache_inval_i, 0, 0, 0, 0, 0)

	' Invoke native inspector payload:
	' - Vector: buf + 1 (Bit 0 set for Thumb-2 state)
	' - Arg 1:  h_title handle
	' - Arg 2:  h_status handle
	' - Arg 3:  expected_nonce (passed for challenge validation, 0 = unverified)
	' - Arg 4..5: Explicit zeros
	ret_val = ExecuteEventProcedure("exec", buf + 1, h_title, h_status, expected_nonce, 0, 0)

	' Free RAM buffer immediately: strings were copied into message descriptors
	FreeMemory(buf)

	' Evaluate return sentinel
	if ret_val = 1464423428 then
		' 0x57495404 = CONTINUATION_ATTEMPTED
		' Explicitly record that continuation confirmation is pending separate evidence
		run_inspector = 4
	else
		if ret_val = 1464423426 then
			' 0x57495402 = CORE_REACHED
			run_inspector = 2
		else
			if ret_val = 1464423425 then
				' 0x57495401 = LOADER_REACHED
				run_inspector = 1
			else
				if ret_val = 1464423679 then
					' 0x574954FF = STALE_OR_FRESHNESS_UNKNOWN
					run_inspector = -1
				else
					' 0x574954EE = INVALID
					run_inspector = 0
				end if
			end if
		end if
	end if
end sub

private sub Initialize()
	setup()
	if h_title > 19 then
		exit sub
	end if
	if h_status > 19 then
		exit sub
	end if

	compat = check_compat()
	if compat = 0 then
		LCDMsg_SetStr(h_title, "PORT-1G: ERR_COMPAT")
		LCDMsg_SetStr(h_status, "FIRMWARE MISMATCH")
		exit sub
	end if

	res = run_inspector()

	' Non-blocking completion: zero polling, zero Wait().
	' Message descriptors are intentionally retained in firmware RAM for
	' Live View inspection in Shooting mode. Total dynamic footprint is
	' strictly bounded to 112 bytes (two 56-byte descriptors).
end sub
