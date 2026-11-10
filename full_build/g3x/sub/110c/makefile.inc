# CHDK platform sub-configuration for Canon PowerShot G3 X GM1.10C (Full Build)

MEMISOSTART=0x3489b4

# OPT_ARAM_MALLOC, ARAM_HEAP_START, and ARAM_HEAP_SIZE removed per memory ownership verification:
# 0x006CE000..0x006F0000 is AdditionAgent's file-read buffer (VERIFIED: docs/CHDK_PORT1A_MEMORY_OWNERSHIP.md:70-78).
# OPT_ARAM_MALLOC is explicitly unset/empty so CHDK uses the Canon allocator (canon_malloc)
# and no heap is allocated in 0x006CE000..0x006F0000.
override OPT_ARAM_MALLOC=
override OPT_CHDK_IN_ARAM=
