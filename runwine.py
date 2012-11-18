#!/usr/bin/env python
import os
import sys
import subprocess

pyver = "%s.%s" % sys.version_info[:2]
pyver0 = "%s" % sys.version_info[0]

os.environ['PATH'] += ";c:\\MinGW\\bin-ccache;c:\\MinGW\\bin"
os.environ['PYTHONPATH'] = "s:\\py%s;s:\\wine\\py%s" % (pyver0, pyver)
os.environ['MINGW'] = "c:\\MinGW"
os.environ['OPT'] = "-ggdb"
os.environ['FOPT'] = "-ggdb"
os.environ['BLAS'] = "s:\\wine\\libblas.a"
os.environ['LAPACK'] = "s:\\wine\\liblapack.a"

subprocess.call([sys.executable] + sys.argv[1:])
