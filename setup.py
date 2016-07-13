import cx_Freeze
import sys
import Pmw
import os

base = None


if sys.platform == 'win32':
	base = 'Win32GUI'

executables = [cx_Freeze.Executable('Mouse House.py', base=base,
	icon='mouse_rec_icon.ico')]

cx_Freeze.setup(name='Mouse House',
	options={'build_exe':{'packages':['Tkinter','u6','Pmw','tkFont','numpy',
	'flycapture2a','tkMessageBox','PIL','LabJackPython','sys'], 'excludes': ['collections.abc'],
	'include_files':'mouse_rec_icon.ico'}}, 
	version='0.13', description='Fear 1 Mouse Stimuli Config. and Recorder',
	author='TiangeLi',
	executables=executables)