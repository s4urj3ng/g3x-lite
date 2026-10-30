' G3X Lite -- BOOT-001B Diagnostic Minimal Native LCD Output Loader
' Target: Canon PowerShot G3 X, Firmware GM1.10C (Platform ID 0x32A8)
' Status: Candidate offline-reviewed minimal native LCD diagnostic loader.
'         Requires explicit owner approval before SD copy or camera execution.
'         NOT APPROVED FOR HARDWARE EXECUTION.
' Note:   Allocates 52 bytes of RAM, loads Thumb-2 non-leaf payload from
'         A/BOOT001B.BIN, synchronizes L1 Harvard caches, passes dedicated
'         native message handle (msg_nat) to exec, verifies return sentinel
'         0x47335832 (1194547250) on telemetry handle (msg_telem), and exits
'         non-blocking without deleting descriptors to allow human inspection
'         in Shooting mode Live View.
'
' DUAL-WINDOW PROOF SEPARATION (Claude F2 / C1):
' - msg_telem (y=160): Managed 100% by Canon Basic. Reports discrete stage
'   telemetry and proves return sentinel verification ("B1:5 RET_OK").
' - msg_nat (y=200): Pre-initialized to "NATIVE: PENDING". Passed in r0 to
'   native payload. Updated ONLY by native call to LCDMsg_SetStr_native.
'   Canon Basic NEVER touches or overwrites msg_nat after exec.
'
' CLEANUP AND LIFETIME (Alternative B):
' - Zero global purge: LCDMsg_Delete(100) is strictly forbidden.
' - Bounded dynamic footprint: exactly two 56-byte descriptors (112 bytes total).
' - Single-attempt session rule: one execution per camera power session.
' - Volatile DRAM reset on normal camera power-off.

DIM payload_size = 52
DIM expected_magic = 1194547250
DIM cache_clean_d = 0xfc127a85
DIM cache_inval_i = 0xfc127b2b
DIM msg_telem = 255
DIM msg_nat = 255

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
	msg_telem = LCDMsg_Create()
	if msg_telem < 0 then
		msg_telem = 255
		exit sub
	end if
	if msg_telem > 19 then
		msg_telem = 255
		exit sub
	end if
	msg_nat = LCDMsg_Create()
	if msg_nat < 0 then
		msg_nat = 255
		exit sub
	end if
	if msg_nat > 19 then
		msg_nat = 255
		exit sub
	end if
	if msg_telem = msg_nat then
		msg_nat = 255
		exit sub
	end if
	LCDMsg_Move(msg_telem, 10, 160)
	LCDMsg_ChangeColor(msg_telem, 2)
	LCDMsg_Move(msg_nat, 10, 200)
	LCDMsg_ChangeColor(msg_nat, 1)
	LCDMsg_SetStr(msg_telem, "B1:1 START")
	LCDMsg_SetStr(msg_nat, "NATIVE: PENDING")
end sub

private sub run_poc()
	run_poc = 0
	buf = AllocateMemory(payload_size)
	if buf = 0 then
		LCDMsg_SetStr(msg_telem, "B1:ERR_ALLOC")
		LCDMsg_SetStr(msg_nat, "NATIVE: NOT_RUN")
		exit sub
	end if

	fh = Fopen_Fut("A/BOOT001B.BIN", "rb")
	if fh = 0 then
		LCDMsg_SetStr(msg_telem, "B1:ERR_OPEN")
		LCDMsg_SetStr(msg_nat, "NATIVE: NOT_RUN")
		FreeMemory(buf)
		exit sub
	end if

	read_sz = Fread_Fut(buf, 1, payload_size, fh)
	cl = Fclose_Fut(fh)
	if read_sz <> payload_size then
		LCDMsg_SetStr(msg_telem, "B1:ERR_READ")
		LCDMsg_SetStr(msg_nat, "NATIVE: NOT_RUN")
		FreeMemory(buf)
		exit sub
	end if
	if cl <> 0 then
		LCDMsg_SetStr(msg_telem, "B1:ERR_CLOSE")
		LCDMsg_SetStr(msg_nat, "NATIVE: NOT_RUN")
		FreeMemory(buf)
		exit sub
	end if

	LCDMsg_SetStr(msg_telem, "B1:3 LOAD_OK")

	' Synchronize L1 Harvard caches prior to native execution:
	' 0xFC127A85: Clean entire L1 D-Cache by set/way (DCCSW)
	' 0xFC127B2B: Invalidate entire L1 I-Cache & branch predictors (ICIALLU)
	ExecuteEventProcedure("exec", cache_clean_d, 0, 0, 0, 0, 0)
	ExecuteEventProcedure("exec", cache_inval_i, 0, 0, 0, 0, 0)

	' Invoke native payload:
	' - Vector: buf + 1 (Bit 0 set mandatory for Thumb-2 state)
	' - Arg 1:  msg_nat handle (passed in r0 to native payload)
	' - Args 2..5: Explicit zeros (populates r1..r3 and stack cleanly)
	ret_val = ExecuteEventProcedure("exec", buf + 1, msg_nat, 0, 0, 0, 0)

	' Free RAM buffer immediately: string was copied into message object
	FreeMemory(buf)

	if ret_val = expected_magic then
		run_poc = 1
		LCDMsg_SetStr(msg_telem, "B1:5 RET_OK")
		' Note: Native payload has called LCDMsg_SetStr_native to post
		' "BOOT-001B: NATIVE PASS" to msg_nat.
		' Do NOT touch or overwrite msg_nat here!
	else
		LCDMsg_SetStr(msg_telem, "B1:ERR_RET")
	end if
end sub

private sub Initialize()
	setup()
	if msg_telem > 19 then
		exit sub
	end if
	if msg_nat > 19 then
		exit sub
	end if

	compat = check_compat()
	if compat = 0 then
		LCDMsg_SetStr(msg_telem, "B1:ERR_COMPAT")
		LCDMsg_SetStr(msg_nat, "NATIVE: NOT_RUN")
		exit sub
	end if
	LCDMsg_SetStr(msg_telem, "B1:2 COMPAT_OK")

	res = run_poc()

	' Non-blocking completion: no Wait(5000), no LCDMsg_Delete
	' Message descriptors are intentionally retained in firmware RAM for
	' Live View inspection in Shooting mode. Total dynamic footprint is
	' strictly bounded to 112 bytes (two 56-byte descriptors).
	' Reclaimed cleanly on normal camera power-off.
end sub
