SVN_BASE_REVISION=$(shell git log|sed -n -e '/git-svn-id:.*@\([0-9]\+\)/{s/.*@//;s/ .*//;p;q}')
GIT_REVISION=$(shell git log|sed -e '1{s/commit \(......\).*/\1/;q;}')
REVISION=$(SVN_BASE_REVISION)+$(GIT_REVISION)

PYVER=2.6

all: build test egg-install

all-wine: build-wine test-wine

build: build-linux
test: test-linux

test-all: test-linux test-wine
build-all: build-linux build-wine

TEST_MODULE=numpy
TEST_STANZA='import sys, os; sys.path.insert(0, os.path.join(os.getcwd(), "site-packages")); import $(TEST_MODULE) as tst; sys.exit(not tst.test("full", verbose=2).wasSuccessful())'

export OPT="-ggdb"

SEPARATE_COMPILATION=1
ifeq ($(SEPARATE_COMPILATION),1)
    export NPY_SEPARATE_COMPILATION=1
endif

build-linux:
	@echo "version = \"$(REVISION)\"" > numpy/core/__svn_version__.py
	@echo "--- Building..."
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

cgdb-linux:
	@echo "--- Testing in Linux"
	cd dist/linux/lib/python$(PYVER) && cgdb --args python$(PYVER) -c $(TEST_STANZA)


build-wine:
	@echo "--- Building..."
	wine c:\\Python25\\python.exe setupwin.py build --compiler=mingw32 install --prefix="dist\\win32" \
		> build.log 2>&1 || { cat build.log; exit 1; }

test-wine:
	@echo "--- Testing in WINE"
	(cd dist/win32/Lib && wine c:\\Python25\\python.exe -c $(TEST_STANZA)) \
		> test.log 2>&1 || { cat test.log; exit 1; }

clean:
	rm -rf build/lib.* build/src.* build/temp.* build/scripts.* dist
	rm -rf build/py3k/build/lib.* build/py3k/build/src.* build/py3k/build/temp.* build/py3k/build/scripts.*

.PHONY: test build test-linux build-linux test-wine build-wine cgdb-linux
