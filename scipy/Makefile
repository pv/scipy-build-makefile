REVISION="$(shell git svn log|head -n2|tail -n1|perl -n -e 'print $$1 if /^r(\d+)/;').$(shell git log|head -n1|awk '{print $$2}')"

all: build test

all-wine: build-wine test-wine

build: build-linux
test: test-linux

test-all: test-linux test-wine
build-all: build-linux build-wine

PYVER=2.6

TEST_STANZA='import sys, os; sys.path.insert(0, os.path.join(os.getcwd(), "site-packages")); import scipy; sys.exit(not scipy.test("full", verbose=2).wasSuccessful())'

build-linux:
	@echo "version = \"$(REVISION)\"" > scipy/__svn_version__.py
	@echo "--- Building..."
	python$(PYVER) setup.py build --debug install --prefix=$(CURDIR)/dist/linux \
		> build.log 2>&1 || { cat build.log; exit 1; }

test-linux:
	@echo "--- Testing in Linux"
	(cd dist/linux/lib/python$(PYVER) && python$(PYVER) -c $(TEST_STANZA)) \
		> test.log 2>&1 || { cat test.log; exit 1; }

build-wine:
	@echo "--- Building..."
	wine c:\\Python25\\python.exe setup.py build --compiler=mingw32 install --prefix="dist\\win32" \
		> build.log 2>&1 || { cat build.log; exit 1; }

test-wine:
	@echo "--- Testing in WINE"
	(cd dist/win32/Lib && wine c:\\Python25\\python.exe -c $(TEST_STANZA)) \
		> test.log 2>&1 || { cat test.log; exit 1; }

clean:
	rm -rf build dist

.PHONY: test build test-linux build-linux test-wine build-wine clean
