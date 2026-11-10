# CHDK platform sub-configuration for Canon PowerShot G3 X GM1.10C (Full Build)

MEMISOSTART=0x3489b4

# ARAM heap values extracted from ROM @ 0xFC05B454 and 0xFC55888C
ARAM_HEAP_START=0x006ce000
ARAM_HEAP_SIZE=0x00022000

override OPT_ARAM_MALLOC=1
override OPT_CHDK_IN_ARAM=
