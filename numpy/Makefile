SVN_BASE_REVISION=$(shell git log|sed -n -e '/git-svn-id:.*@\([0-9]\+\)/{s/.*@//;s/ .*//;p;q}')
GIT_REVISION=$(shell git log|sed -e '1{s/commit \(......\).*/\1/;q;}')
REVISION=$(SVN_BASE_REVISION)+$(GIT_REVISION)

PYVER=2.7

all: build test

all-wine: build-wine test-wine

build: build-linux
test: test-linux

test-all: test-linux test-wine
build-all: build-linux build-wine

TEST_MODULE=numpy
TEST_TYPE=full
TEST_STANZA='import sys, os; sys.path.insert(0, os.path.join(os.getcwd(), "site-packages")); import $(TEST_MODULE) as tst; sys.exit(not tst.test("$(TEST_TYPE)", verbose=2).wasSuccessful())'

DEBUG=1
ifeq ($(DEBUG),1)
    export OPT="-ggdb"
endif

PATH := /usr/lib/ccache:/usr/local/lib/f90cache:$(PATH)
export PATH

USE_2TO3CACHE=1
export USE_2TO3CACHE

SEPARATE_COMPILATION=1
ifeq ($(SEPARATE_COMPILATION),1)
    export NPY_SEPARATE_COMPILATION=1
endif

WINEPREFIX=/home/pauli/.wine/sub/python
export WINEPREFIX

LANG=C
export LANG

LD_LIBRARY_PATH=$(CURDIR)/libndarray/.libs
export LD_LIBRARY_PATH

PYWINVER=$(subst .,,$(PYVER))

build-linux:
	@echo "version = \"$(REVISION)\"" > numpy/core/__svn_version__.py
	@echo "--- Building..."
	test ! -d libndarray || ((if test ! -f libndarray/Makefile; then cd libndarray && ./autogen.sh && CFLAGS="-ggdb" ./configure; fi) && make -C libndarray)
	python$(PYVER) setup.py build --debug install --prefix=$(CURDIR)/dist/linux \
		> build.log 2>&1 || { cat build.log; exit 1; }

EGGDIR=$(CURDIR)/dist/linux/lib/python$(PYVER)/site-packages

egg-install:
	install -d $(EGGDIR)
	PYTHONPATH=$(EGGDIR) \
	        python$(PYVER) setupegg.py install --prefix=$(CURDIR)/dist/linux \
	        > install.log 2>&1 || { cat build.log; exit 1; }
	rm -rf $(EGGDIR)/numpy
	ln -s `ls -FAd --sort=time $(EGGDIR)/*.egg|head -n1`/numpy $(EGGDIR)/numpy
	find $(CURDIR)/dist -name 'test_*.py' -print0|xargs -0r chmod a-x

test-linux:
	@echo "--- Testing in Linux"
	(cd dist/linux/lib/python$(PYVER) && python$(PYVER) -c $(TEST_STANZA)) \
		> test.log 2>&1 || { cat test.log; exit 1; }

cgdb:
	@echo "--- Testing in Linux"
	cd dist/linux/lib/python$(PYVER) && cgdb --args python$(PYVER) -c $(TEST_STANZA)


build-wine:
	@echo "--- Building..."
	rm -rf dist/win32
	wine c:\\Python$(PYWINVER)\\python.exe setupwin.py build --compiler=mingw32 install --prefix="dist\\win32" \
		> build.log 2>&1 || { cat build.log; exit 1; }

test-wine:
	@echo "--- Testing in WINE"
	(cd dist/win32/Lib && wine c:\\Python$(PYWINVER)\\python.exe -c $(TEST_STANZA)) \
		> test.log 2>&1 || { cat test.log; exit 1; }

python-wine:
	cd dist/win32/Lib && wine c:\\Python$(PYWINVER)\\python.exe

ipython:
	cd $(CURDIR)/dist && PYTHONPATH=$$PYTHONPATH:$(CURDIR)/dist/linux/lib/python$(PYVER)/site-packages python$(PYVER) `which ipython`

cgdb-python:
	cd $(CURDIR)/dist && PYTHONPATH=$$PYTHONPATH:$(CURDIR)/dist/linux/lib/python$(PYVER)/site-packages cgdb --args python$(PYVER) $(PYARGS)

python:
	cd $(CURDIR)/dist && PYTHONPATH=$$PYTHONPATH:$(CURDIR)/dist/linux/lib/python$(PYVER)/site-packages python$(PYVER) $(PYARGS)

sh:
	cd $(CURDIR)/dist && PYTHONPATH=$$PYTHONPATH:$(CURDIR)/dist/linux/lib/python$(PYVER)/site-packages bash

etags:
	find numpy libndarray -name '*.[ch]' -o -name '*.src' \
	| ctags-exuberant -L - \
	-e --extra=+fq --fields=+afiksS --c++-kinds=+px \
	--langmap=c:+.src,python:+.pyx --if0=yes \
	--regex-c="/#define ([a-zA-Z0-9@_]*@[a-zA-Z0-9@_]*)/\1/" \
	--regex-c="/^([a-zA-Z0-9@_]*@[a-zA-Z0-9@_]*)\(/\1/"

tags: etags

watch:
	while true; do \
	    inotifywait -e modify --exclude '.*~' -r $(CURDIR)/numpy && \
		{ make PYVER=$(PYVER) TEST_TYPE="$(TEST_TYPE)" TEST_MODULE="$(TEST_MODULE)" etags build test; }; \
	done

clean:
	rm -rf build dist

.PHONY: test build test-linux build-linux test-wine build-wine cgdb-linux
