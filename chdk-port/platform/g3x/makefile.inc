# CHDK platform configuration for Canon PowerShot G3 X
# Target: GM1.10C, Platform ID 0x32A8 (12968 decimal)

ifeq ($(G3X_GUI_NOOVERDRAW),1)
ifneq ($(G3X_GUI_DBUF),1)
$(error G3X_GUI_NOOVERDRAW=1 requires G3X_GUI_DBUF=1)
endif
CFLAGS += -DG3X_GUI_NOOVERDRAW=1
endif

# mandatory for DIGIC 6
THUMB_FW=1

PLATFORMID=12968

PLATFORMOS=dryos

PLATFORMOSVER=57

# mandatory for DIGIC 6
MEMBASEADDR=0x8000

# start of firmware
ROMBASEADDR=0xFC000000

# end of RAM
MAXRAMADDR=0x0fffffff

# RomStarter @ 0xFC0005C6 and DryOS StartDiskboot @ 0xFC05BC3C decode DISKBOOT.BIN
# using dancingbits row 13 (DWORD tables @ 0xFC0044D4 and 0xFC7C0F8C).
NEED_ENCODED_DISKBOOT=13

# PLATFORMID @ 0xFDF20270

# Found @FC003FC8 & @FCC8FD64
KEYSYS=d5

# generated FI2 needs word-based checksum
FI2FLAGS=W

DIGIC=60
