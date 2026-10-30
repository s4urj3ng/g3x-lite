' G3X Lite -- VIDEO-001 MovieRecorder State & Limit Diagnostic Probe (Read-Only)
' Target: Canon PowerShot G3 X, Firmware GM1.10C (Platform ID 0x32A8)
' Status: Candidate read-only diagnostic probe requiring independent review.
'         Performs no recorder-state writes (modifies only its allocated heap
'         buffer, transient LCD message state, and appends to A/VIDEO001.LOG).
' Note:   Extended video recording is NOT_FEASIBLE via one-shot Playback Canon
'         Basic because MovieRecorder_SetupModeAndLimits (0xFC097D72) reloads
'         ROM literals (#1799/#3599) on every recording start. The recorder
'         enforces an internal 4 GiB size policy check (0xFC098BAA).
'         Values read in Playback mode reflect boot .data or post-recording residue.

DIM mr_stop_reason = 0x0000c0c0
DIM mr_rec_state = 0x0000c0c8
DIM mr_warn_sec = 0x0000c0e4
DIM mr_elapsed_sec = 0x0000c1b4
DIM mr_max_frames = 0x0000c274
DIM mr_cur_frames = 0x0000c278
DIM mr_stream_bytes_lo = 0x0000c298
DIM rom_mr_state_lit = 0xfc097b6c
DIM rom_mr_task_lit = 0xfc09af50
DIM expected_mr_base = 0x0000c078
DIM expected_mr_task = 0xfc09ac19
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
	if strcmp("MovieRecorder.c", 0xfc097b80) <> 0 then
		exit sub
	end if
	if strcmp("MovieRecord", 0xfc09af54) <> 0 then
		exit sub
	end if
	if *rom_mr_state_lit <> expected_mr_base then
		exit sub
	end if
	if *rom_mr_task_lit <> expected_mr_task then
		exit sub
	end if
	check_compat = 1
end sub

private sub write_log()
	write_log = 0
	logbuf = AllocateMemory(128)
	if logbuf <> 0 then
		logf = Fopen_Fut("A/VIDEO001.LOG", "a")
		if logf <> 0 then
			sprintf(logbuf, "st=%d stop=%d\n", *mr_rec_state, *mr_stop_reason)
			w1 = Fwrite_Fut(logbuf, strlen(logbuf), 1, logf)
			sprintf(logbuf, "el=%d warn=%d\n", *mr_elapsed_sec, *mr_warn_sec)
			w2 = Fwrite_Fut(logbuf, strlen(logbuf), 1, logf)
			sprintf(logbuf, "curf=%d maxf=%d\n", *mr_cur_frames, *mr_max_frames)
			w3 = Fwrite_Fut(logbuf, strlen(logbuf), 1, logf)
			sprintf(logbuf, "bytes=%08X\n", *mr_stream_bytes_lo)
			w4 = Fwrite_Fut(logbuf, strlen(logbuf), 1, logf)
			cl = Fclose_Fut(logf)
			if w1 = 1 then
				if w2 = 1 then
					if w3 = 1 then
						if w4 = 1 then
							if cl = 0 then
								write_log = 1
							end if
						end if
					end if
				end if
			end if
		end if
		FreeMemory(logbuf)
	end if
end sub

private sub setup()
	System.Create()
	UI.CreatePublic()
	msg = LCDMsg_Create()
	if msg <> 255 then
		LCDMsg_Move(msg, 10, 200)
		LCDMsg_ChangeColor(msg, 2)
		Wait(10)
		LCDMsg_SetStr(msg, "VIDEO-001 GM1.10C")
	end if
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
	logged = write_log()
	Wait(100)
	if msg <> 255 then
		if logged = 1 then
			LCDMsg_SetStr(msg, "VIDEO-001 Probe OK")
		else
			LCDMsg_SetStr(msg, "Log Write Failed")
		end if
	end if
end sub
