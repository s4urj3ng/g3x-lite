' G3X Lite -- UI-001A Minimal Static Native Menu Loader
' Target: Canon PowerShot G3 X, Firmware GM1.10C (Platform ID 0x32A8)
' Status: Candidate offline-reviewed minimal static native menu loader.
'         Requires explicit owner approval before SD copy or camera execution.
'         NOT APPROVED FOR HARDWARE EXECUTION.
' Note:   Allocates 156 bytes of RAM, loads Thumb-2 non-leaf payload from
'         A/UI001A.BIN, synchronizes L1 Harvard caches, passes 3 pre-allocated
'         LCDMsg handles (h_title, h_item1, h_item2) to exec, verifies return
'         sentinel 0x47335834 (1194547252), and exits immediately (< 50 ms)
'         without blocking or looping to allow prompt mode transition to
'         Shooting mode Live View.
'
' THREE-HANDLE STATIC LAYOUT (Claude C1):
' - h_title (x=60, y=100): Color 2 (Green), "G3X Lite - Main Menu"
' - h_item1 (x=60, y=140): Color 1 (White), "> System Info"
' - h_item2 (x=60, y=180): Color 1 (White), "  Settings"
'
' SCOPED CLEANUP AND LIFETIME (Claude C3 / B1):
' - Zero global purge: LCDMsg_Delete(100) is strictly forbidden.
' - Order-correct partial rollback: on allocation failure, deletes only
'   handles created by the current invocation in reverse order.
' - Bounded dynamic footprint: exactly three 56-byte descriptors (168 bytes total).
' - Single-attempt session rule: one execution per camera power session.
' - Volatile DRAM reset on normal camera power-off.

DIM payload_size = 156
DIM expected_magic = 1194547252
DIM cache_clean_d = 0xfc127a85
DIM cache_inval_i = 0xfc127b2b
DIM h_title = 255
DIM h_item1 = 255
DIM h_item2 = 255

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

	h_item1 = LCDMsg_Create()
	if h_item1 < 0 then
		LCDMsg_Delete(h_title)
		h_title = 255
		h_item1 = 255
		exit sub
	end if
	if h_item1 > 19 then
		LCDMsg_Delete(h_title)
		h_title = 255
		h_item1 = 255
		exit sub
	end if

	h_item2 = LCDMsg_Create()
	if h_item2 < 0 then
		LCDMsg_Delete(h_item1)
		LCDMsg_Delete(h_title)
		h_title = 255
		h_item1 = 255
		h_item2 = 255
		exit sub
	end if
	if h_item2 > 19 then
		LCDMsg_Delete(h_item1)
		LCDMsg_Delete(h_title)
		h_title = 255
		h_item1 = 255
		h_item2 = 255
		exit sub
	end if

	if h_title = h_item1 then
		LCDMsg_Delete(h_item2)
		LCDMsg_Delete(h_item1)
		LCDMsg_Delete(h_title)
		h_title = 255
		h_item1 = 255
		h_item2 = 255
		exit sub
	end if
	if h_item1 = h_item2 then
		LCDMsg_Delete(h_item2)
		LCDMsg_Delete(h_item1)
		LCDMsg_Delete(h_title)
		h_title = 255
		h_item1 = 255
		h_item2 = 255
		exit sub
	end if
	if h_title = h_item2 then
		LCDMsg_Delete(h_item2)
		LCDMsg_Delete(h_item1)
		LCDMsg_Delete(h_title)
		h_title = 255
		h_item1 = 255
		h_item2 = 255
		exit sub
	end if

	LCDMsg_Move(h_title, 60, 100)
	LCDMsg_Move(h_item1, 60, 140)
	LCDMsg_Move(h_item2, 60, 180)
	LCDMsg_SetStr(h_title, "UI001A: INIT")
	LCDMsg_SetStr(h_item1, "ITEM 1: PENDING")
	LCDMsg_SetStr(h_item2, "ITEM 2: PENDING")
end sub

private sub run_poc()
	run_poc = 0
	buf = AllocateMemory(payload_size)
	if buf = 0 then
		LCDMsg_SetStr(h_title, "UI001A: ERR_ALLOC")
		LCDMsg_SetStr(h_item1, "NOT RUN")
		LCDMsg_SetStr(h_item2, "NOT RUN")
		exit sub
	end if

	fh = Fopen_Fut("A/UI001A.BIN", "rb")
	if fh = 0 then
		LCDMsg_SetStr(h_title, "UI001A: ERR_OPEN")
		LCDMsg_SetStr(h_item1, "NOT RUN")
		LCDMsg_SetStr(h_item2, "NOT RUN")
		FreeMemory(buf)
		exit sub
	end if

	read_sz = Fread_Fut(buf, 1, payload_size, fh)
	cl = Fclose_Fut(fh)
	if read_sz <> payload_size then
		LCDMsg_SetStr(h_title, "UI001A: ERR_READ")
		LCDMsg_SetStr(h_item1, "NOT RUN")
		LCDMsg_SetStr(h_item2, "NOT RUN")
		FreeMemory(buf)
		exit sub
	end if
	if cl <> 0 then
		LCDMsg_SetStr(h_title, "UI001A: ERR_CLOSE")
		LCDMsg_SetStr(h_item1, "NOT RUN")
		LCDMsg_SetStr(h_item2, "NOT RUN")
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
	' - Arg 2:  h_item1 handle (passed in r1 to native payload)
	' - Arg 3:  h_item2 handle (passed in r2 to native payload)
	' - Args 4..5: Explicit zeros (populates r3 and stack cleanly)
	ret_val = ExecuteEventProcedure("exec", buf + 1, h_title, h_item1, h_item2, 0, 0)

	' Free RAM buffer immediately: strings were copied into message descriptors
	FreeMemory(buf)

	if ret_val = expected_magic then
		run_poc = 1
		' Note: Native payload has updated h_title, h_item1, h_item2 via
		' native LCDMsg_ChangeColor_native and LCDMsg_SetStr_native.
		' Do NOT touch or overwrite handles on success!
	else
		LCDMsg_SetStr(h_title, "UI001A: ERR_SENTINEL")
		LCDMsg_SetStr(h_item1, "SENTINEL FAIL")
		LCDMsg_SetStr(h_item2, "SENTINEL FAIL")
	end if
end sub

private sub Initialize()
	setup()
	if h_title > 19 then
		exit sub
	end if
	if h_item1 > 19 then
		exit sub
	end if
	if h_item2 > 19 then
		exit sub
	end if

	compat = check_compat()
	if compat = 0 then
		LCDMsg_SetStr(h_title, "UI001A: ERR_COMPAT")
		LCDMsg_SetStr(h_item1, "NOT RUN")
		LCDMsg_SetStr(h_item2, "NOT RUN")
		exit sub
	end if

	res = run_poc()

	' Non-blocking completion: zero Wait, zero polling loop.
	' Exactly three 56-byte message descriptors (168 bytes total)
	' are intentionally retained in firmware RAM for Live View inspection
	' upon switching to Shooting mode. Reclaimed on camera power-off.
end sub
