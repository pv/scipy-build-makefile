#!/usr/bin/env python
"""
git bisect run python bisectrun.py SCRIPT [PRE_SCRIPT]

Run a Python script under Git bisect, rebuilding the module and
arranging import paths first. If build fails, it is reported to Git as
'cannot test'.

The script should raise an AssertionError if it fails, or run
successfully.  Any other errors raised are reported to Git as 'cannot
test'.

The script is run after the build, with import path correctly set up.
The pre-script is run before the build, without setting the import
path.

"""
import sys
import os
import subprocess
import optparse
import shutil
from distutils.sysconfig import get_python_lib

ENV = {
    'OPT': '-ggdb',
    'FOPT': '-ggdb',
    'NPY_SEPARATE_BUILD': '1',
    'USE_2TO3CACHE': '1',
    'PATH': '/usr/lib/ccache:/usr/local/lib/f90cache' + os.pathsep + os.environ['PATH'],
}

def main():
    p = optparse.OptionParser(usage=__doc__.strip())
    p.add_option("-n", "--no-clean", dest="no_clean", action="store_true",
                 default=False, help="do not remove the build directory")
    options, args = p.parse_args()

    if len(args) == 1:
        script = os.path.abspath(args[0])
        pre_script = None
    elif len(args) == 2:
        script = os.path.abspath(args[0])
        pre_script = os.path.abspath(args[1])
    else:
        p.error('wrong number of input arguments')

    # -- Run pre script first
    if pre_script is not None:
        try:
            exec_script(pre_script)
        except AssertionError, e:
            print "TEST: failed:", e
            sys.exit(1)
        except BaseException, e:
            print "TEST: cannot run:", e
            sys.exit(125)

    # -- Rebuild and arrange import path
    try:
        sitedir, dstdir = build_and_install(no_clean=options.no_clean)
    except RuntimeError:
        # Signal testing failure
        print "TEST: cannot run: build failed"
        sys.exit(125)

    sys.path.insert(0, sitedir)

    # -- Run test script
    try:
        exec_script(script)
    except AssertionError, e:
        print "TEST: failed:", e
        sys.exit(1)
    except BaseException, e:
        print "TEST: cannot run:", e
        sys.exit(125)

    print "TEST: success"
    sys.exit(0)

def exec_script(filename):
    cwd = os.getcwd()
    try:
        f = open(filename, 'rb')
        code = compile(f.read(), filename, 'exec')
        f.close()
        exec code in {}
    finally:
        os.chdir(cwd)

def build_and_install(no_clean=False):
    dstdir = os.path.abspath(os.path.join(os.path.dirname(__file__), "testdist"))
    sitedir = get_python_lib(prefix=dstdir)

    if os.path.isdir('build') and not no_clean:
        shutil.rmtree('build')
    if os.path.isdir(sitedir):
        shutil.rmtree(sitedir)
    os.makedirs(sitedir)

    print "Building..."
    log = open('build.log', 'wb')
    p = subprocess.Popen([sys.executable, 'setup.py', 'install',
                          '--prefix=' + dstdir], env=ENV,
                          stdout=log, stderr=log)
    p.communicate()
    log.close()

    if p.returncode != 0:
        raise RuntimeError()

    return sitedir, dstdir

if __name__ == "__main__":
    main()
