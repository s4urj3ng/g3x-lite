' G3X Lite -- HDMI-001 Clean HDMI / Clean Rec-Mode Overlay (RAM-only)
' Target: Canon PowerShot G3 X, Firmware GM1.10C (Platform ID 0x32A8)
' Status: Offline-reviewed hardware-test candidate. Requires explicit owner
'         approval before SD copy or execution. Not proven on hardware.
' Restore: second run copies the ROM default Palette 0 back. This is NOT a
'          byte-exact restore of runtime-customised entries (see
'          docs/HDMI001_INDEPENDENT_REVIEW.md). Power cycle is authoritative.

DIM palette_control = 0x00015da4
DIM palette_init_flag = 0x00015db0
DIM active_palette_index = 0x00015db4
DIM palette_buffer_ptr = 0x00015dbc
DIM expected_table_addr = 0x001231b8
DIM expected_magic = 0xfc77b62c
DIM rom_default_pal0 = 0xfc77c8b0
DIM slot_min = 0x00001000
DIM slot_max = 0x10000000
DIM palette_to_zero = 0
DIM msg = 0
DIM slot_seen = 0
DIM entry1_seen = 0
DIM bak_ok = 0

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

private sub toggle_palette()
	toggle_palette = 0
	if *palette_init_flag <> 1 then
		exit sub
	end if
	tbl = *palette_buffer_ptr
	if tbl <> expected_table_addr then
		exit sub
	end if
	slot_ptr = tbl + (palette_to_zero * 4)
	slot = *slot_ptr
	slot_seen = slot
	if slot = 0 then
		exit sub
	end if
	if slot < slot_min then
		exit sub
	end if
	if slot >= slot_max then
		exit sub
	end if
	if *slot <> expected_magic then
		exit sub
	end if
	payload = slot + 4
	entry1 = slot + 8
	entry2 = slot + 12
	entry3 = slot + 16
	entry1_seen = *entry1
	is_clean = 0
	if *entry1 = 0 then
		if *entry2 = 0 then
			if *entry3 = 0 then
				is_clean = 1
			end if
		end if
	end if
	if is_clean = 0 then
		bak = Fopen_Fut("A/G3XPAL0.BAK", "w")
		if bak <> 0 then
			Fwrite_Fut(payload, 1024, 1, bak)
			Fclose_Fut(bak)
			bak_ok = 1
		end if
		memset(payload, 0, 1024)
		Poke8(palette_control, 3)
		toggle_palette = 1
	else
		memcpy(payload, rom_default_pal0, 1024)
		Poke8(palette_control, 3)
		toggle_palette = 2
	end if
end sub

private sub write_log(state)
	logbuf = AllocateMemory(80)
	if logbuf <> 0 then
		sprintf(logbuf, "st=%d idx=%d slot=%08X e1=%08X bak=%d\n", state, *active_palette_index, slot_seen, entry1_seen, bak_ok)
		logf = Fopen_Fut("A/HDMI001.LOG", "a")
		if logf <> 0 then
			Fwrite_Fut(logbuf, strlen(logbuf), 1, logf)
			Fclose_Fut(logf)
		end if
		FreeMemory(logbuf)
	end if
end sub

private sub setup()
	System.Create()
	UI.CreatePublic()
	msg = LCDMsg_Create()
	LCDMsg_Move(msg, 10, 200)
	LCDMsg_ChangeColor(msg, 2)
	Wait(10)
	LCDMsg_SetStr(msg, "HDMI-001 GM1.10C")
end sub

private sub Initialize()
	setup()
	compat = check_compat()
	if compat = 0 then
		Wait(100)
		LCDMsg_SetStr(msg, "Not GM1.10C!")
	else
		Wait(100)
		state = toggle_palette()
		write_log(state)
		if state = 1 then
			LCDMsg_SetStr(msg, "Overlay disabled!")
		end if
		if state = 2 then
			LCDMsg_SetStr(msg, "Overlay ROM-restored!")
		end if
		if state = 0 then
			LCDMsg_SetStr(msg, "Palette guard abort!")
		end if
	end if
	Wait(500)
end sub
