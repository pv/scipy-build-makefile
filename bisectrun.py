#!/usr/bin/env python
"""
git bisect run bisectrun.py SCRIPT

Run a Python script under Git bisect, running "make clean build" and arranging
import paths first. If build fails, it is reported to Git as 'cannot test'.

The script should raise an AssertionError if it fails, or run successfully.
Any other errors raised are reported to Git as 'cannot test'.

"""
import sys
import os
import optparse

def main():
    p = optparse.OptionParser(usage=__doc__.strip())
    options, args = p.parse_args()

    if len(args) != 1:
        p.error('no script file given')

    script = os.path.abspath(args[0])

    # -- Build and import
    pyver = "%d.%d" % sys.version_info[:2]

    os.chdir(os.path.abspath(os.path.dirname(__file__)))
    ret = os.system("make clean build PYVER=%s" % pyver)

    if ret != 0:
        # Signal testing failure
        print "TEST: cannot run: build failed"
        sys.exit(125)

    pth = os.path.abspath(os.path.join(os.path.dirname(__file__),
        "dist", "linux", "lib", "python%s" % pyver, "site-packages"))
    sys.path.insert(0, pth)

    # -- Run test

    try:
        execfile(script)
    except AssertionError, e:
        print "TEST: failed:", e
        sys.exit(1)
    except BaseException, e:
        print "TEST: cannot run:", e
        sys.exit(125)

    print "TEST: success"
    sys.exit(0)

if __name__ == "__main__":
    main()
