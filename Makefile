PYVER=2.7

all: build test

all-wine: build-wine test-wine

build: build-linux
test: test-linux

test-all: test-linux test-wine
build-all: build-linux build-wine

ifeq ($(shell test -d $(CURDIR)/scipy && echo "1"),1)
MODULENAME=scipy
else
MODULENAME=numpy
endif

TEST_MODULE=$(MODULENAME)
TEST_TYPE=full
TEST_STANZA='import sys, os; sys.path.insert(0, os.path.join(os.getcwd(), "site-packages")); import $(TEST_MODULE) as tst; sys.exit(not tst.test("$(TEST_TYPE)", verbose=2).wasSuccessful())'

DEBUG=1
ifeq ($(DEBUG),1)
    SETUP_PY_BUILDFLAG=--debug
    export OPT="-ggdb"
    export FOPT="-ggdb -O1"
endif

CCACHE=1
ifeq ($(CCACHE),1)
    PATH := /usr/lib/ccache:/usr/local/lib/f90cache:$(PATH)
    export PATH
endif

USE_2TO3CACHE=1
export USE_2TO3CACHE

SEPARATE_COMPILATION=1
ifeq ($(SEPARATE_COMPILATION),1)
    export NPY_SEPARATE_COMPILATION=1
endif

WINE=wine

WINEPREFIX=$(HOME)/.wine/sub/python
export WINEPREFIX

LANG=C
export LANG

ifeq ($(MODULENAME),numpy)
LD_LIBRARY_PATH=$(CURDIR)/libndarray/.libs
export LD_LIBRARY_PATH
endif

PYWINVER=$(subst .,,$(PYVER))

EGGDIR=$(CURDIR)/dist/linux/lib/python$(PYVER)/site-packages

NCPUS=$(shell grep '^processor' /proc/cpuinfo|wc -l)

PYPY_HOME=$(HOME)/prj/external/pypy

PYPY_BIN=pypy-c
PYPY_C=$(PYPY_HOME)/pypy/translator/goal/$(PYPY_BIN)
PYPYPY=$(PYPY_C) $(PYPY_HOME)/pypy/bin/py.py 
PYPYPY_FLAGS=\
	--withmod-cpyext --withmod-_hashlib --withmod-time --withmod-_socket \
	--withmod-select --withmod-signal --withmod-mmap --withmod-cStringIO \
	--withmod-unicodedata --withmod-thread

#export PYTHONPATH=$(CURDIR)/../numpy/dist/linux/lib/python$(PYVER)/site-packages/

#
# -- Build and install
#

build-linux-bento:
	@echo "--- Building..."
ifeq ($(MODULENAME),numpy)
	test ! -d libndarray || ((if test ! -f libndarray/Makefile; then cd libndarray && ./autogen.sh && CFLAGS="-ggdb" ./configure; fi) && make -C libndarray)
endif
	bentomaker configure --prefix=$(CURDIR)/dist/linux \
		> build.log 2>&1 || { cat build.log; exit 1; }
	bentomaker build -j $(NCPUS) \
		>> build.log 2>&1 || { cat build.log; exit 1; }
	bentomaker install \
		>> build.log 2>&1 || { cat build.log; exit 1; }

build-linux:
	@echo "--- Building..."
ifeq ($(MODULENAME),numpy)
	test ! -d libndarray || ((if test ! -f libndarray/Makefile; then cd libndarray && ./autogen.sh && CFLAGS="-ggdb" ./configure; fi) && make -C libndarray)
endif
	python$(PYVER) setup.py build $(SETUP_PY_BUILDFLAG) install --prefix=$(CURDIR)/dist/linux \
		> build.log 2>&1 || { cat build.log; exit 1; }

pypy-nose:
	test -d $(CURDIR)/dist/linux/site-packages/nose-1.1.2-py2.7.egg \
	|| (install -d $(CURDIR)/dist/linux/site-packages; \
	    cp -af nose-dist/* $(CURDIR)/dist/linux/site-packages/)

build-pypy: pypy-nose
	$(PYPY_C) setup.py install --prefix=$(CURDIR)/dist/linux

build-pypypy: pypy-nose
	$(PYPYPY) $(PYPYPY_FLAGS) \
		setup.py install --prefix=$(CURDIR)/dist/linux

build-pypypy-pre: pypy-nose
	$(PYPY_C) $(PYPY_HOME)/pypy/module/cpyext/presetup.py \
		setup.py install --prefix=$(CURDIR)/dist/linux

build-pypypy-all: pypy-nose
	$(PYPYPY) --allworkingmodules \
		setup.py install --prefix=$(CURDIR)/dist/linux

egg-install:
	install -d $(EGGDIR)
	PYTHONPATH=$(EGGDIR) \
	        python$(PYVER) setupegg.py install --prefix=$(CURDIR)/dist/linux \
	        > install.log 2>&1 || { cat build.log; exit 1; }
	rm -rf $(EGGDIR)/$(MODULENAME)
	ln -s `ls -FAd --sort=time $(EGGDIR)/*.egg|head -n1`/$(MODULENAME) $(EGGDIR)/$(MODULENAME)
	find $(CURDIR)/dist -name 'test_*.py' -print0|xargs -0r chmod a-x

build-wine:
	@echo "--- Building..."
	rm -rf dist/win32
	$(WINE) c:\\Python$(PYWINVER)\\python.exe setupwin.py build --compiler=mingw32 install --prefix="dist\\win32" \
		> build.log 2>&1 || { cat build.log; exit 1; }

#
# -- Run tests
#

test-linux:
	@echo "--- Testing in Linux"
	(cd dist/linux/lib/python$(PYVER) && python$(PYVER) -c $(TEST_STANZA)) \
		> test.log 2>&1 || { cat test.log; exit 1; }

test-wine:
	@echo "--- Testing in WINE"
	(cd dist/win32/Lib && $(WINE) c:\\Python$(PYWINVER)\\python.exe -c $(TEST_STANZA)) \
		> test.log 2>&1 || { cat test.log; exit 1; }

# -- Launch debugger

cgdb-test:
	@echo "--- Testing in Linux"
	cd dist/linux/lib/python$(PYVER) && cgdb --args python$(PYVER) -c $(TEST_STANZA)

cgdb-python:
	cd $(CURDIR)/dist && PYTHONPATH=$$PYTHONPATH:$(CURDIR)/dist/linux/lib/python$(PYVER)/site-packages cgdb --args python$(PYVER) $(PYARGS)


PYPYX_STR="import sys; sys.path.insert(0, \"/home/pauli/prj/scipy/numpy/dist/linux/site-packages/\"); import numpy as np; np.test(verbose=2)"

pypyx:
	make pypy PYARGS='-c $(PYPYX_STR)'

cgdb-pypyx:
	make cgdb-pypy PYARGS='-c $(PYPYX_STR)'

cgdb-pypy:
	cd $(CURDIR)/dist && PYTHONPATH=$$PYTHONPATH:$(CURDIR)/dist/linux/site-packages cgdb --args $(PYPY_C) $(PYARGS)

cgdb-pypypy:
	cd $(CURDIR)/dist && PYTHONPATH=$$PYTHONPATH:$(CURDIR)/dist/linux/site-packages cgdb --args $(PYPYPY) $(PYPYPY_FLAGS) $(PYARGS)

cgdb-pypypy-all:
	cd $(CURDIR)/dist && PYTHONPATH=$$PYTHONPATH:$(CURDIR)/dist/linux/site-packages cgdb --args $(PYPYPY) --allworkingmodules $(PYARGS)

# -- Launch valgrind

VALGRIND=valgrind-py

valgrind-test:
	@echo "--- Testing in Linux"
	cd dist/linux/lib/python$(PYVER) && $(VALGRIND) python$(PYVER) -c $(TEST_STANZA)

valgrind-python:
	cd $(CURDIR)/dist && PYTHONPATH=$$PYTHONPATH:$(CURDIR)/dist/linux/lib/python$(PYVER)/site-packages $(VALGRIND) python$(PYVER) $(PYARGS)

#
# -- Launch python shell
#

python-wine:
	cd dist/win32/Lib && $(WINE) c:\\Python$(PYWINVER)\\python.exe

ipython:
	cd $(CURDIR)/dist && PYTHONPATH=$$PYTHONPATH:$(CURDIR)/dist/linux/lib/python$(PYVER)/site-packages python$(PYVER) `which ipython`

python:
	cd $(CURDIR)/dist && PYTHONPATH=$$PYTHONPATH:$(CURDIR)/dist/linux/lib/python$(PYVER)/site-packages python$(PYVER) $(PYARGS)

pypy:
	cd $(CURDIR)/dist && PYTHONPATH=$$PYTHONPATH:$(CURDIR)/dist/linux/site-packages $(PYPY_C) $(PYARGS)

pypypy:
	cd $(CURDIR)/dist && PYTHONPATH=$$PYTHONPATH:$(CURDIR)/dist/linux/site-packages $(PYPYPY) $(PYPYPY_FLAGS) $(PYARGS)

pypypy-all:
	cd $(CURDIR)/dist && PYTHONPATH=$$PYTHONPATH:$(CURDIR)/dist/linux/site-packages $(PYPYPY) --allworkingmodules $(PYARGS)

#
# -- Launch shell
#

sh:
	cd $(CURDIR)/dist && PYTHONPATH=$$PYTHONPATH:$(CURDIR)/dist/linux/lib/python$(PYVER)/site-packages bash

#
# -- Other commands
#

etags:
	find $(MODULENAME) libndarray -name '*.[ch]' -o -name '*.src' -o -name '*.py' \
	| ctags-exuberant -L - \
	-e --extra=+fq --fields=+afiksS --c++-kinds=+px \
	--langmap=c:+.src,python:+.pyx --if0=yes \
	--regex-c="/#define ([a-zA-Z0-9@_]*@[a-zA-Z0-9@_]*)/\1/" \
	--regex-c="/^([a-zA-Z0-9@_]*@[a-zA-Z0-9@_]*)\(/\1/"

tags: etags

watch:
	while true; do \
	    inotifywait -e modify --exclude '.*~' -r $(CURDIR)/$(MODULENAME) && \
		{ make PYVER=$(PYVER) TEST_TYPE="$(TEST_TYPE)" TEST_MODULE="$(TEST_MODULE)" etags build test; }; \
	done

clean:
	rm -rf build dist

oclean:
	rm -rf dist
	rm -rf build/scripts.*
	find build \( -name '*.o' -o -name '*.a' \
	    -o -name '*.so' -o -name '*.py*' \) -a -type f -print0 \
	| xargs -0r rm -f

.PHONY: all all-wine build-all build build-linux build-wine cgdb-python \
	cgdb-test clean egg-install etags ipython python python-wine \
	sh tags test-all test-linux test test-wine watch oclean
