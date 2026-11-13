.PHONY: all port45_no_overdraw port44_dbuf port43_dbuf default test test_port45 clean

PYTHON ?= python3

all: port45_no_overdraw

port45_no_overdraw:
	$(PYTHON) -B scripts/build_port45_no_overdraw.py

port44_dbuf:
	$(PYTHON) -B tools/build_port44_dbuf_heap.py

port43_dbuf:
	$(PYTHON) -B scripts/build_port43_dbuf.py

test_port45:
	$(PYTHON) -B scripts/test_port45_no_overdraw.py

test: test_port45
	$(PYTHON) -B -m unittest discover -s tests -p 'test_*.py'

clean:
	rm -rf out/port45-no-overdraw
