' Canon Basic activation and SD write probe
' Expected output: A/CBPROBE.TXT

DIM probe_file=0

private sub Initialize()
	System.Create()
	probe_file = Fopen_Fut("A/CBPROBE.TXT","w")
	if probe_file <> 0 then
		Fwrite_Fut("G3X_CBASIC_PROBE_OK\n",20,1,probe_file)
		Fclose_Fut(probe_file)
	end if
end sub
