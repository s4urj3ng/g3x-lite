' G3X Lite -- BOOT-001A Minimal Native Execution Loader
' Target: Canon PowerShot G3 X, Firmware GM1.10C (Platform ID 0x32A8)
' Status: Candidate offline-reviewed minimal native execution proof of concept.
'         Requires explicit owner approval before SD copy or camera execution.
'         Not proven on hardware.
' Note:   Loads 12-byte Thumb-2 leaf function from A/BOOT001A.BIN into allocated
'         RAM, synchronizes L1 Harvard caches, passes five explicit zero arguments
'         to exec, and checks that the returned value is exactly 0x47335831
'         (decimal 1194547249). Contains zero hardware writes and zero hooks.

DIM payload_size = 12
DIM expected_magic = 1194547249
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
	if msg <> 255 then
		LCDMsg_Move(msg, 10, 200)
		LCDMsg_ChangeColor(msg, 2)
		Wait(10)
		LCDMsg_SetStr(msg, "BOOT-001A GM1.10C")
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

	fh = Fopen_Fut("A/BOOT001A.BIN", "rb")
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

	' Synchronize L1 Harvard caches prior to execution:
	' 0xFC127A85: Clean entire L1 D-Cache by set/way
	' 0xFC127B2B: Invalidate entire L1 I-Cache & branch predictors
	ExecuteEventProcedure("exec", cache_clean_d, 0, 0, 0, 0, 0)
	ExecuteEventProcedure("exec", cache_inval_i, 0, 0, 0, 0, 0)

	' Invoke native payload: Bit 0 set (buf + 1) is mandatory for Thumb-2 state!
	' Pass 5 explicit zero arguments to populate r0..r3 and stack arg cleanly.
	ret_val = ExecuteEventProcedure("exec", buf + 1, 0, 0, 0, 0, 0)

	if ret_val = expected_magic then
		run_poc = 1
		if msg <> 255 then
			LCDMsg_SetStr(msg, "BOOT-001A: PASS (0x47335831)")
		end if
	else
		if msg <> 255 then
			LCDMsg_SetStr(msg, "BOOT-001A: FAIL (Bad Return)")
		end if
	end if

	FreeMemory(buf)
end sub

private sub Initialize()
	setup()
	compat = check_compat()
	if compat = 0 then
		Wait(100)
		if msg <> 255 then
			LCDMsg_SetStr(msg, "Not GM1.10C!")
		end if
		exit sub
	end if
	res = run_poc()
	Wait(3000)
end sub
