# Makefile for platform/g3x (Full Build)
topdir=../../
include $(topdir)makefile_cam.inc

CFLAGS += -DG3X_FULL_BUILD=1 -DG3X_DISABLE_CARD_WRITES=1 -DCAM_SUPPORT_BITMAP_RES_CHANGE=1 -DOPT_DISABLE_FILE_WRITES=1 -UOPT_FILEIO_STATS -DG3X_GUI5=1 -I$(topdir)platform/generic
OBJS = main.o lib.o wrappers.o kbd.o shooting.o platform_palette.o

all: libplatform.a

platform_palette.o: $(topdir)platform/generic/palette.c
	@echo $< \-\> $@
	$(CC) $(CFLAGS) -nostdinc -c -o $@ $<

libplatform.a: $(OBJS)
	@echo $^ \-\> $@
	$(AR) rcs $@ $^

clean:
	rm -f *.o *.a

include $(topdir)bottom.inc
