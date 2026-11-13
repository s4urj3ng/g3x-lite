ifeq ($(G3X_GUI_NOOVERDRAW),1)
ifneq ($(G3X_GUI_DBUF),1)
$(error G3X_GUI_NOOVERDRAW=1 requires G3X_GUI_DBUF=1)
endif
CFLAGS += -DG3X_GUI_NOOVERDRAW=1
endif

include ../makefile_platform.inc

