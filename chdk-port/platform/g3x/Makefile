ifeq ($(G3X_GUI_DIAG),1)
ifneq ($(G3X_GUI_DBUF),1)
$(error G3X_GUI_DIAG=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1)
endif
ifneq ($(G3X_GUI_NOOVERDRAW),1)
$(error G3X_GUI_DIAG=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1)
endif
ifneq ($(G3X_KBD_CHECK),1)
$(error G3X_GUI_DIAG=1 requires G3X_GUI_DBUF=1 G3X_GUI_NOOVERDRAW=1 G3X_KBD_CHECK=1)
endif
CFLAGS += -DG3X_GUI_DIAG=1
endif

ifeq ($(G3X_KBD_CHECK),1)
ifneq ($(G3X_GUI_DBUF),1)
$(error G3X_KBD_CHECK=1 requires G3X_GUI_DBUF=1)
endif
endif

ifeq ($(G3X_GUI_NOOVERDRAW),1)
ifneq ($(G3X_GUI_DBUF),1)
$(error G3X_GUI_NOOVERDRAW=1 requires G3X_GUI_DBUF=1)
endif
CFLAGS += -DG3X_GUI_NOOVERDRAW=1
endif

include ../makefile_platform.inc

ifeq ($(G3X_KBD_CHECK),1)
CFLAGS += -DG3X_KBD_CHECK=1
endif


