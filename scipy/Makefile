SVN_BASE_REVISION=$(shell git log|sed -n -e '/git-svn-id:.*@\([0-9]\+\)/{s/.*@//;s/ .*//;p;q}')
GIT_REVISION=$(shell git log|sed -e '1{s/commit \(......\).*/\1/;q;}')
REVISION=$(SVN_BASE_REVISION)+$(GIT_REVISION)

all: build test

all-wine: build-wine test-wine

build: build-linux
test: test-linux

test-all: test-linux test-wine
build-all: build-linux build-wine

PYVER=2.7

DEBUG=1
ifeq ($(DEBUG),1)
export OPT=-ggdb
export FOPT=-ggdb -O1
endif

export PYTHONPATH=$(CURDIR)/../numpy/dist/linux/lib/python$(PYVER)/site-packages/

CCACHE=1
ifeq ($(CCACHE),1)
PATH := /usr/lib/ccache:/usr/local/lib/f90cache:$(PATH)
export PATH
endif

USE_2TO3CACHE=1
export USE_2TO3CACHE

WINEPREFIX=/home/pauli/.wine/sub/python
export WINEPREFIX

LANG=C
export LANG

TEST_MODULE=scipy
TEST_TYPE=full
TEST_STANZA='import sys, os; sys.path.insert(0, os.path.join(os.getcwd(), "site-packages")); import $(TEST_MODULE) as tst; sys.exit(not tst.test("$(TEST_TYPE)", verbose=2).wasSuccessful())'

build-linux:
	@echo "version = \"$(REVISION)\"" > scipy/__svn_version__.py
	@echo "--- Building..."
	python$(PYVER) setup.py build --debug install --prefix=$(CURDIR)/dist/linux \
		> build.log 2>&1 || { cat build.log; exit 1; }

build-linux-scons:
	@echo "version = \"$(REVISION)\"" > scipy/__svn_version__.py
	@echo "--- Building..."
	python$(PYVER) setupscons.py build --debug install --prefix=$(CURDIR)/dist/linux \
		> build.log 2>&1 || { cat build.log; exit 1; }

test-linux:
	@echo "--- Testing in Linux"
	(cd dist/linux/lib/python$(PYVER) && python$(PYVER) -c $(TEST_STANZA)) \
		> test.log 2>&1 || { cat test.log; exit 1; }

test-cgdb:
	@echo "--- Testing in Linux"
	cd dist/linux/lib/python$(PYVER) && cgdb --args python$(PYVER) -c $(TEST_STANZA)

test-valgrind:
	@echo "--- Testing in Linux"
	(cd dist/linux/lib/python$(PYVER) && valgrind --suppressions=$(HOME)/.valgrind/valgrind-python.supp -- python$(PYVER) -c $(TEST_STANZA)) > test.log 2>&1 || { cat test.log; exit 1; }

egg-install:
	install -d $(CURDIR)/dist/linux/lib/python$(PYVER)/site-packages
	PYTHONPATH=$$PYTHONPATH:$(CURDIR)/dist/linux/lib/python$(PYVER)/site-packages \
	    python$(PYVER) setupegg.py install --prefix=$(CURDIR)/dist/linux \
	    > install.log 2>&1 || { cat install.log; exit 1; }
	find $(CURDIR)/dist -name 'test_*.py' -print0|xargs -0r chmod a-x

build-wine:
	@echo "--- Building..."
	wine c:\\Python25\\python.exe setup.py build --compiler=mingw32 install --prefix="dist\\win32" \
		> build.log 2>&1 || { cat build.log; exit 1; }

test-wine:
	@echo "--- Testing in WINE"
	(cd dist/win32/Lib && wine c:\\Python25\\python.exe -c $(TEST_STANZA)) \
		> test.log 2>&1 || { cat test.log; exit 1; }

ipython:
	cd $(CURDIR)/dist && PYTHONPATH=$$PYTHONPATH:$(CURDIR)/dist/linux/lib/python$(PYVER)/site-packages python$(PYVER) `which ipython` -pylab

cgdb:
	cd $(CURDIR)/dist && PYTHONPATH=$$PYTHONPATH:$(CURDIR)/dist/linux/lib/python$(PYVER)/site-packages cgdb --args python$(PYVER) $(PYARGS)

python:
	cd $(CURDIR)/dist && PYTHONPATH=$$PYTHONPATH:$(CURDIR)/dist/linux/lib/python$(PYVER)/site-packages python$(PYVER) $(PYARGS)

python-valgrind:
	cd $(CURDIR)/dist && PYTHONPATH=$$PYTHONPATH:$(CURDIR)/dist/linux/lib/python$(PYVER)/site-packages valgrind --suppressions=$(HOME)/.valgrind/valgrind-python.supp -- python$(PYVER) $(PYARGS)

sh:
	cd $(CURDIR)/dist && PYTHONPATH=$$PYTHONPATH:$(CURDIR)/dist/linux/lib/python$(PYVER)/site-packages bash

etags:
	find scipy -name '*.[ch]' -o -name '*.src' -o -name '*.py' -o -name '*.pyx' \
	| ctags-exuberant -L - \
	-e --extra=+fq --fields=+afiksS --c++-kinds=+px \
	--langmap=c:+.src,python:+.pyx --if0=yes \
	--regex-c="/#define ([a-zA-Z0-9@_]*@[a-zA-Z0-9@_]*)/\1/" \
	--regex-c="/^([a-zA-Z0-9@_]*@[a-zA-Z0-9@_]*)\(/\1/"

tags: etags

clean:
	rm -rf build dist

.PHONY: test build test-linux build-linux test-wine build-wine clean etags tags
