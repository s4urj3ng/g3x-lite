' G3X Lite -- BOOT-001B Minimal Native LCD Output Loader
' Target: Canon PowerShot G3 X, Firmware GM1.10C (Platform ID 0x32A8)
' Status: Candidate offline-reviewed minimal native LCD output proof of concept.
'         Requires explicit owner approval before SD copy or camera execution.
'         NOT APPROVED FOR HARDWARE EXECUTION.
' Note:   Allocates 52 bytes of RAM, loads Thumb-2 non-leaf payload from
'         A/BOOT001B.BIN, synchronizes L1 Harvard caches, passes message handle
'         to exec, verifies native LCD string update, checks return sentinel
'         0x47335832 (1194547250), and executes clean teardown.
'
' IMPORTANT PROOF DISTINCTION (F2):
' Return sentinel 0x47335832 (decimal 1194547250) verifies ONLY that the native
' code executed and returned cleanly. It does NOT prove the LCD display succeeded.
' The sole proof of the native LCD function call is the visible on-screen banner:
' "BOOT-001B: NATIVE PASS".

DIM payload_size = 52
DIM expected_magic = 1194547250
DIM cache_clean_d = 0xfc127a85
DIM cache_inval_i = 0xfc127b2b
DIM msg = 255

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
	msg = LCDMsg_Create()
	if msg < 0 then
		msg = 255
		exit sub
	end if
	if msg > 19 then
		msg = 255
		exit sub
	end if
	LCDMsg_Move(msg, 10, 200)
	LCDMsg_ChangeColor(msg, 2)
	Wait(10)
	LCDMsg_SetStr(msg, "BOOT-001B: READY")
end sub

private sub teardown()
	if msg <> 255 then
		LCDMsg_Delete(msg)
		msg = 255
	end if
end sub

private sub run_poc()
	run_poc = 0
	buf = AllocateMemory(payload_size)
	if buf = 0 then
		if msg <> 255 then
			LCDMsg_SetStr(msg, "Alloc Failed")
		end if
		exit sub
	end if

	fh = Fopen_Fut("A/BOOT001B.BIN", "rb")
	if fh = 0 then
		if msg <> 255 then
			LCDMsg_SetStr(msg, "Open Failed")
		end if
		FreeMemory(buf)
		exit sub
	end if

	read_sz = Fread_Fut(buf, 1, payload_size, fh)
	cl = Fclose_Fut(fh)
	if read_sz <> payload_size then
		if msg <> 255 then
			LCDMsg_SetStr(msg, "Read Size Mismatch")
		end if
		FreeMemory(buf)
		exit sub
	end if
	if cl <> 0 then
		if msg <> 255 then
			LCDMsg_SetStr(msg, "Close Failed")
		end if
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
	' - Arg 1:  msg handle (passed in r0 to native payload)
	' - Args 2..5: Explicit zeros (populates r1..r3 and stack cleanly)
	ret_val = ExecuteEventProcedure("exec", buf + 1, msg, 0, 0, 0, 0)

	' Free RAM buffer immediately: string was copied into message object
	FreeMemory(buf)

	if ret_val = expected_magic then
		run_poc = 1
		' Note: Native payload has called LCDMsg_SetStr_native to post
		' "BOOT-001B: NATIVE PASS" to the UI redraw queue.
		' Do NOT overwrite the message banner here so the native text remains visible!
	else
		if msg <> 255 then
			LCDMsg_SetStr(msg, "BOOT-001B: BAD RET")
		end if
	end if
end sub

private sub Initialize()
	setup()
	if msg = 255 then
		exit sub
	end if
	compat = check_compat()
	if compat = 0 then
		Wait(100)
		LCDMsg_SetStr(msg, "Not GM1.10C!")
		Wait(3000)
		teardown()
		exit sub
	end if

	res = run_poc()

	' Bounded human observation window (5 seconds)
	' Allows visual inspection of native LCD banner: "BOOT-001B: NATIVE PASS"
	Wait(5000)

	' Clean restoration: delete OSD message object
	teardown()
end sub
