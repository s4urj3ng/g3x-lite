.PHONY: all port59_movie_combined port45_no_overdraw port44_dbuf port43_dbuf default test test_port45 clean

unexport MAKEFLAGS
unexport MAKELEVEL

PYTHON ?= python3

all: port45_no_overdraw

port59_movie_combined:
	$(PYTHON) -B scripts/build_port43_dbuf.py --no-overdraw --kbd-check --gui-diag --shadow2 --gui-sync --gui-menu --gui-restore2 --playback-menu --movie-status --movie-nolimit --movie-autocont --movie-autocont-ui --out-dir out/port59-movie-combined

port45_no_overdraw:
	$(PYTHON) -B scripts/build_port45_no_overdraw.py

port44_dbuf:
	$(PYTHON) -B tools/build_port44_dbuf_heap.py

port43_dbuf:
	$(PYTHON) -B scripts/build_port43_dbuf.py

test_port45:
	$(PYTHON) -B scripts/test_port45_no_overdraw.py

test: test_port45
	env -u MAKEFLAGS -u MAKELEVEL $(PYTHON) -B -m unittest tests/test_port44_dbuf_heap.py

clean:
	rm -rf out/port45-no-overdraw

