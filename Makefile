PY ?= python3

hello:
	$(PY) src/cshs.py run examples/hello.c##

list:
	$(PY) src/cshs.py run examples/list_demo.c##

fib:
	$(PY) src/cshs.py run examples/fib.c##
