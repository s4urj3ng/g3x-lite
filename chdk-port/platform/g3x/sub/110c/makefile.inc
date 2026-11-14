# CHDK platform sub-configuration for Canon PowerShot G3 X GM1.10C

# MEMISOSTART represents the candidate load address of the CHDK core in RAM.
# finsig_thumb2 identified candidate MEMISOSTART = 0x3489b4 (DryOS BSS limit @ 0xFC0200DC).
# In accordance with Codex review and CHDK-PORT-0 safety rules, this placement is
# UNVERIFIED and NOT APPROVED for camera execution.
# Retained as documentation candidate pending memory ownership verification.
MEMISOSTART=0x3489b4

# ARAM heap values extracted from ROM @ 0xFC05B454 and 0xFC55888C
ARAM_HEAP_START=0x006ce000
ARAM_HEAP_SIZE=0x00022000

override OPT_ARAM_MALLOC=1
override OPT_CHDK_IN_ARAM=

ifeq ($(G3X_GUI_SYNC),1)
ifneq ($(G3X_GUI_DBUF),1)
$(error G3X_GUI_SYNC=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)
endif
ifneq ($(G3X_GUI_NOOVERDRAW),1)
$(error G3X_GUI_SYNC=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)
endif
ifneq ($(G3X_KBD_CHECK),1)
$(error G3X_GUI_SYNC=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)
endif
ifneq ($(G3X_GUI_DIAG),1)
$(error G3X_GUI_SYNC=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)
endif
ifneq ($(G3X_GUI_SHADOW2),1)
$(error G3X_GUI_SYNC=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1 G3X_GUI_DIAG=1 G3X_GUI_SHADOW2=1)
endif
ifeq ($(findstring -DG3X_GUI_SYNC=1,$(CFLAGS)),)
CFLAGS += -DG3X_GUI_SYNC=1
endif
endif
