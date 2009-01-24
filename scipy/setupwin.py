#!/usr/bin/env python
import os
os.environ['PATH'] += ";c:\\MinGW\\bin;c:\\Python25"
os.environ['MINGW'] = "c:\\MinGW"
execfile('setup.py')
