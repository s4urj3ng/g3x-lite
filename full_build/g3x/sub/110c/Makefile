topdir=../../../../
include $(topdir)makefile_cam.inc

CORE_OBJS = main.thm.o gui_draw.thm.o memmgmt.thm.o gui.thm.o kbd_process.thm.o \
            kbd_common.thm.o conf.thm.o gui_osd.thm.o raw.thm.o usb_sync.thm.o \
            shooting.thm.o camera_info.thm.o remotecap.thm.o lib_thumb.thm.o \
            lang_str.thm.o ptp.thm.o gui_menu.thm.o

CFLAGS += -DG3X_FULL_BUILD=1 -DG3X_DISABLE_CARD_WRITES=1 -DCAM_SUPPORT_BITMAP_RES_CHANGE=1 -DOPT_DISABLE_FILE_WRITES=1 -UOPT_FILEIO_STATS -DG3X_GUI5=1 -I$(topdir)platform/generic
OBJS = boot.o stubs_min.o stubs_auto.o stubs_entry.o stubs_entry_2.o capt_seq.o movie_rec.o filewrite.o
LDOPTS = -nostdlib -Wl,--allow-shlib-undefined -Wl,-EL,-T,$(tools)/link-boot.ld \
         -Wl,-N,-Ttext,$(MEMISOSTART) \
         -Wl,--wrap=conf_save -Wl,--wrap=save_params_values -Wl,--wrap=save_int_value_file \
         -Wl,--wrap=write -Wl,--wrap=fwrite -Wl,--wrap=open -Wl,--wrap=fopen -Wl,--wrap=creat \
         -Wl,--wrap=mkdir -Wl,--wrap=MakeDirectory_Fut -Wl,--wrap=_MakeDirectory_Fut \
         -Wl,--wrap=remove -Wl,--wrap=DeleteFile_Fut -Wl,--wrap=_DeleteFile_Fut \
         -Wl,--wrap=DeleteDirectory_Fut -Wl,--wrap=_DeleteDirectory_Fut \
         -Wl,--wrap=rename -Wl,--wrap=RenameFile_Fut -Wl,--wrap=_RenameFile_Fut

all: main.bin

entry.o: $(core)/entry.S
	@echo $< \-\> $@
	$(CC) $(CFLAGS) -nostdinc -c -o $@ $<

lang_str.thm.o: $(topdir)lib/lang/lang_str.c
	@echo $< \-\> $@
	$(CC) $(CFLAGS) -mthumb -nostdinc -c -o $@ $<

gui_menu.thm.o: $(cam)/gui_menu.c
	@echo $< \-\> $@
	$(CC) $(CFLAGS) -mthumb -nostdinc -c -o $@ $<

libplatformsub.a: $(OBJS) $(CORE_OBJS)
	@echo $^ \-\> $@
	$(AR) rcs $@ $^

main.elf: entry.o $(cam)/libplatform.a libplatformsub.a
	@echo \-\> $@
	$(CC) $(CFLAGS) -o $@ -Wl,--start-group entry.o $(cam)/libplatform.a libplatformsub.a \
		$(topdir)lib/font/.o2/libfont.a \
		$(topdir)lib/math/.o2/libmath.a \
		$(topdir)lib/lang/.o2/liblang.a \
		$(topdir)lib/armutil/.o2/libarmutil.a \
		$(topdir)lib/core/.o2/libcore.a \
		-lgcc -Wl,--end-group $(LDOPTS)

main.bin: main.elf
	@echo $< \-\> $@
	$(OBJCOPY) -O binary $< $@

clean:
	rm -f *.o *.a *.bin *.elf *.dump *.elf.syms

include $(topdir)bottom.inc
