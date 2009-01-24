
REVISION="$(shell git svn log|head -n2|tail -n1|perl -n -e 'print $$1 if /^r(\d+)/;').$(shell git log|head -n1|awk '{print $$2}')"

all: build test egg-install

build: build-linux
test: test-linux

test-all: test-linux test-wine
build-all: build-linux build-wine

TEST_STANZA='import sys, os; sys.path.insert(0, os.path.join(os.getcwd(), "site-packages")); import numpy; sys.exit(numpy.test(verbose=2))'

build-linux:
	@echo "version = \"$(REVISION)\"" > numpy/core/__svn_version__.py
	@echo "--- Building..."
	python2.5 setup.py build --debug install --prefix=dist/linux \
		> build.log 2>&1 || { cat build.log; exit 1; }

egg-install:
	install -d $(PWD)/dist/linux/lib/python2.5/site-packages
	PYTHONPATH=$(PWD)/dist/linux/lib/python2.5/site-packages \
		python2.5 setupegg.py install --prefix=$(PWD)/dist/linux \
		> install.log 2>&1 || { cat build.log; exit 1; }

test-linux:
	@echo "--- Testing in Linux"
	(cd dist/linux/lib/python2.5 && python -c $(TEST_STANZA)) \
		> test.log 2>&1 || { cat test.log; exit 1; }

build-wine:
	@echo "--- Building..."
	wine c:\\Python25\\python.exe setupwin.py build --compiler=mingw32 install --prefix="dist\\win32" \
		> build.log 2>&1 || { cat build.log; exit 1; }

test-wine:
	@echo "--- Testing in WINE"
	(cd dist/win32/Lib && wine c:\\Python25\\python.exe -c $(TEST_STANZA)) \
		> test.log 2>&1 || { cat test.log; exit 1; }

.PHONY: test build test-linux build-linux test-wine build-wine
