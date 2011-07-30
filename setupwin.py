#!/usr/bin/env python
import os
import sys
import subprocess

os.environ['PATH'] += ";c:\\MinGW\\ccache-bin;c:\\MinGW\\bin"
os.environ['MINGW'] = "c:\\MinGW"
os.environ['OPT'] = "-ggdb"

if sys.version_info[0] >= 3:
    def rep(x):
        return x.replace('dist\\', '..\\..\\dist\\')
else:
    rep = lambda x: x

args = [rep(x) for x in sys.argv[1:]]
subprocess.call([sys.executable, 'setup.py'] + args)
