' G3X Lite -- VIDEO-001A-0 Read-Only Diagnostic Probe Loader
' Target: Canon PowerShot G3 X, Firmware GM1.10C (Platform ID 0x32A8)
' Status: Candidate offline-reviewed read-only telemetry probe loader.
'         Requires explicit owner approval before SD copy or camera execution.
'         NOT APPROVED FOR HARDWARE EXECUTION.
' Note:   Allocates 532 bytes for payload and 32 bytes for caller-owned result
'         memory. Loads Thumb-2 payload from A/VID001A0.BIN, synchronizes L1
'         Harvard caches, passes 3 pre-allocated LCDMsg handles (h_title,
'         h_line1, h_line2) and result_buf to exec, verifies return sentinel
'         0x47335837 (1194547255) and memory canaries, and exits immediately
'         (execution time unmeasured, estimated < 1 ms) without polling to allow
'         mode transition to Shooting mode Live View.
'
' THREE-HANDLE DISPLAY LAYOUT:
' - h_title (x=60, y=100): Color 2 (Green), "VIDEO-001A-0: REC PROBE"
' - h_line1 (x=60, y=140): Color 1 (White), "MAX: XXXXXXXX CUR: YYYYYYYY"
' - h_line2 (x=60, y=180): Color 1 (White), "ST: XXXXXXXX W: YYYYYYYY CAN: OK"
'
' SCOPED CLEANUP AND LIFETIME (Proven UI-001B-0 model):
' - Zero global purge: LCDMsg_Delete(100) is strictly forbidden.
' - Order-correct partial rollback: on handle allocation failure, deletes only
'   handles created by the current invocation in reverse order.
' - Caller-owned result memory: 32-byte DRAM buffer allocated via AllocateMemory(32)
'   and freed via FreeMemory(result_buf) immediately after exec.
' - Bounded dynamic footprint: exactly three 56-byte descriptors (168 bytes total).
' - Single-attempt session rule: one execution per camera power session.
' - Volatile DRAM reset on normal camera power-off.

DIM payload_size = 532
DIM result_size = 32
DIM expected_magic = 1194547255
DIM cache_clean_d = 0xfc127a85
DIM cache_inval_i = 0xfc127b2b
DIM h_title = 255
DIM h_line1 = 255
DIM h_line2 = 255

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

	h_line1 = LCDMsg_Create()
	if h_line1 < 0 then
		LCDMsg_Delete(h_title)
		h_title = 255
		h_line1 = 255
		exit sub
	end if
	if h_line1 > 19 then
		LCDMsg_Delete(h_title)
		h_title = 255
		h_line1 = 255
		exit sub
	end if

	h_line2 = LCDMsg_Create()
	if h_line2 < 0 then
		LCDMsg_Delete(h_line1)
		LCDMsg_Delete(h_title)
		h_title = 255
		h_line1 = 255
		h_line2 = 255
		exit sub
	end if
	if h_line2 > 19 then
		LCDMsg_Delete(h_line1)
		LCDMsg_Delete(h_title)
		h_title = 255
		h_line1 = 255
		h_line2 = 255
		exit sub
	end if

	if h_title = h_line1 then
		LCDMsg_Delete(h_line2)
		LCDMsg_Delete(h_line1)
		LCDMsg_Delete(h_title)
		h_title = 255
		h_line1 = 255
		h_line2 = 255
		exit sub
	end if
	if h_line1 = h_line2 then
		LCDMsg_Delete(h_line2)
		LCDMsg_Delete(h_line1)
		LCDMsg_Delete(h_title)
		h_title = 255
		h_line1 = 255
		h_line2 = 255
		exit sub
	end if
	if h_title = h_line2 then
		LCDMsg_Delete(h_line2)
		LCDMsg_Delete(h_line1)
		LCDMsg_Delete(h_title)
		h_title = 255
		h_line1 = 255
		h_line2 = 255
		exit sub
	end if

	LCDMsg_Move(h_title, 60, 100)
	LCDMsg_Move(h_line1, 60, 140)
	LCDMsg_Move(h_line2, 60, 180)
	LCDMsg_SetStr(h_title, "VID001A0: INIT")
	LCDMsg_SetStr(h_line1, "LINE 1: PENDING")
	LCDMsg_SetStr(h_line2, "LINE 2: PENDING")
end sub

private sub run_poc()
	run_poc = 0
	buf = AllocateMemory(payload_size)
	if buf = 0 then
		LCDMsg_SetStr(h_title, "VID001A0: ERR_ALLOC_P")
		LCDMsg_SetStr(h_line1, "NOT RUN")
		LCDMsg_SetStr(h_line2, "NOT RUN")
		exit sub
	end if

	res_buf = AllocateMemory(result_size)
	if res_buf = 0 then
		LCDMsg_SetStr(h_title, "VID001A0: ERR_ALLOC_R")
		LCDMsg_SetStr(h_line1, "NOT RUN")
		LCDMsg_SetStr(h_line2, "NOT RUN")
		FreeMemory(buf)
		exit sub
	end if

	fh = Fopen_Fut("A/VID001A0.BIN", "rb")
	if fh = 0 then
		LCDMsg_SetStr(h_title, "VID001A0: ERR_OPEN")
		LCDMsg_SetStr(h_line1, "NOT RUN")
		LCDMsg_SetStr(h_line2, "NOT RUN")
		FreeMemory(res_buf)
		FreeMemory(buf)
		exit sub
	end if

	read_sz = Fread_Fut(buf, 1, payload_size, fh)
	cl = Fclose_Fut(fh)
	if read_sz <> payload_size then
		LCDMsg_SetStr(h_title, "VID001A0: ERR_READ")
		LCDMsg_SetStr(h_line1, "NOT RUN")
		LCDMsg_SetStr(h_line2, "NOT RUN")
		FreeMemory(res_buf)
		FreeMemory(buf)
		exit sub
	end if
	if cl <> 0 then
		LCDMsg_SetStr(h_title, "VID001A0: ERR_CLOSE")
		LCDMsg_SetStr(h_line1, "NOT RUN")
		LCDMsg_SetStr(h_line2, "NOT RUN")
		FreeMemory(res_buf)
		FreeMemory(buf)
		exit sub
	end if

	' Synchronize L1 Harvard caches prior to native execution:
	' 0xFC127A85: Clean entire L1 D-Cache by set/way (DCCSW)
	' 0xFC127B2B: Invalidate entire L1 I-Cache & branch predictors (ICIALLU)
	ExecuteEventProcedure("exec", cache_clean_d, 0, 0, 0, 0, 0)
	ExecuteEventProcedure("exec", cache_inval_i, 0, 0, 0, 0, 0)

	' Invoke native payload:
	' - Vector: buf + 1 (Bit 0 set mandatory for Thumb-2 state)
	' - Arg 1:  h_title handle (passed in r0 to native payload)
	' - Arg 2:  h_line1 handle (passed in r1 to native payload)
	' - Arg 3:  h_line2 handle (passed in r2 to native payload)
	' - Arg 4:  res_buf pointer (passed in r3 to native payload)
	' - Arg 5:  Explicit zero (populates stack cleanly)
	ret_val = ExecuteEventProcedure("exec", buf + 1, h_title, h_line1, h_line2, res_buf, 0)

	' Verify caller-owned result memory canaries:
	' Canary 1: offset 0 must equal "CAN1"
	' Canary 2: offset 28 must equal "CAN2"
	can1_ok = memcmp(res_buf, "CAN1", 4)
	can2_ok = memcmp(res_buf + 28, "CAN2", 4)

	' Free RAM buffers immediately: strings were copied into message descriptors
	FreeMemory(res_buf)
	FreeMemory(buf)

	if ret_val = expected_magic then
		if can1_ok <> 0 then
			LCDMsg_SetStr(h_title, "VID001A0: ERR_CAN1")
		else
			if can2_ok <> 0 then
				LCDMsg_SetStr(h_title, "VID001A0: ERR_CAN2")
			else
				run_poc = 1
				' Note: Native payload has updated h_title, h_line1, h_line2 via
				' native LCDMsg_ChangeColor_native and LCDMsg_SetStr_native.
				' Do NOT touch or overwrite handles on success!
			end if
		end if
	else
		LCDMsg_SetStr(h_title, "VID001A0: ERR_SENTINEL")
		LCDMsg_SetStr(h_line1, "SENTINEL FAIL")
		LCDMsg_SetStr(h_line2, "SENTINEL FAIL")
	end if
end sub

private sub Initialize()
	setup()
	if h_title > 19 then
		exit sub
	end if
	if h_line1 > 19 then
		exit sub
	end if
	if h_line2 > 19 then
		exit sub
	end if

	compat = check_compat()
	if compat = 0 then
		LCDMsg_SetStr(h_title, "VID001A0: ERR_COMPAT")
		LCDMsg_SetStr(h_line1, "NOT RUN")
		LCDMsg_SetStr(h_line2, "NOT RUN")
		exit sub
	end if

	res = run_poc()

	' Non-blocking completion: zero Wait, zero polling loop.
	' Exactly three 56-byte message descriptors (168 bytes total)
	' are intentionally retained in firmware RAM for Live View inspection
	' upon switching to Shooting mode. Reclaimed on camera power-off.
end sub
