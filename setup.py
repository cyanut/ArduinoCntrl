import cx_Freeze
import sys
import Pmw

base = None


if sys.platform == 'win32':
	base = 'Win32GUI'

executables = [cx_Freeze.Executable('Mouse Recorder.py', base=base,
	icon='mouse.ico')]

cx_Freeze.setup(name='Mouse Recorder', 
	options={'build_exe':{'packages':['Tkinter','u6','Pmw','tkFont','numpy',
	'flycapture2a','tkMessageBox','PIL','LabJackPython','sys'], 'excludes': ['collections.abc'],
	'include_files':'mouse.ico'}}, 
	version='0.11', description='Fear 1 Mouse Stimuli Config. and Recorder',
	executables=executables)