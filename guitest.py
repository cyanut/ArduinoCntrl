# coding=utf-8
"""
For use with LabJack U6, PTGrey FMVU-03MTC-CS, Arduino UNO
"""
import os
import ast
import sys
import time
import math
import glob
import Queue
import serial
import shutil
import pickle
import calendar
import threading
import multiprocessing
from struct import pack
from pprint import pprint
from copy import deepcopy
from datetime import datetime
from operator import itemgetter

import u6
import Pmw
import tkFont
import numpy as np
import Tkinter as Tk
# noinspection PyUnresolvedReferences
import flycapture2a as fc2
import tkMessageBox as tkMb
from PIL.ImageTk import Image, PhotoImage
from LabJackPython import LowlevelErrorException, LabJackException


################################################################
# To do list:
# - Arduino GUI Geometry fine tuning
# - Arduino optiboot.c loader: remove led flash on start?
# - Debugging of everything that could go wrong
# - adding start/stop conditionals for camera
# - correct status messages for every device for every stage
#################################################################
# Concurrency Controls:
#   (global variables because otherwise we need to create these
#   under the child process and extract as attributes to avoid
#   pickling issues)
# Queues:
MASTER_DUMP_QUEUE = multiprocessing.Queue()
MASTER_GRAPH_QUEUE = multiprocessing.Queue()
THREAD_DUMP_QUEUE = multiprocessing.Queue()
PROCESS_DUMP_QUEUE = multiprocessing.Queue()
# Lock Controls
LJ_READ_READY_LOCK = multiprocessing.Event()
LJ_EXP_READY_LOCK = multiprocessing.Event()
ARD_READY_LOCK = multiprocessing.Event()
CMR_READY_LOCK = multiprocessing.Event()
###################################################################


# Misc. Functions
def format_secs(time_in_secs, report_ms=False, option=None):
    """Turns Seconds into MM:SS"""
    output = ''
    secs = int(time_in_secs) % 60
    mins = int(time_in_secs) // 60
    if report_ms:
        millis = int((time_in_secs - int(time_in_secs)) * 1000)
        output = '{:0>2}:{:0>2}.{:0>3}'.format(mins, secs, millis)
    elif not report_ms:
        output = '{:0>2}:{:0>2}'.format(mins, secs)
    if option == 'min':
        output = '{:0>2}'.format(mins)
    elif option == 'sec':
        output = '{:0>2}'.format(secs)
    return output


def format_daytime(options, dayformat='/', timeformat=':'):
    """Returns day and time in various formats"""
    time_now = datetime.now()
    if options == 'daytime':
        dayformat = '-'
        timeformat = '-'
    day = '{}{}{}{}{}'.format(time_now.year, dayformat,
                              time_now.month, dayformat,
                              time_now.day)
    clock = '{:0>2}{}{:0>2}{}{:0>2}'.format(time_now.hour, timeformat,
                                            time_now.minute, timeformat,
                                            time_now.second)
    if options == 'day':
        return day
    elif options == 'time':
        return clock
    elif options == 'daytime':
        return '{}--{}'.format(day, clock)


def time_diff(start_time, end_time=None, choice='millis'):
    """Returns time difference from starting time"""
    if end_time is None:
        end_time = datetime.now()
    timediff = (end_time - start_time)
    if choice == 'millis':
        return timediff.seconds * 1000 + int(timediff.microseconds) / 1000
    elif choice == 'micros':
        return timediff.seconds * 1000 + float(timediff.microseconds) / 1000


def lim_str_len(string, length, end='...'):
    """Limit a given string to a specified length"""
    if len(string) <= length:
        return string
    else:
        return '{}{}'.format(string[:length - len(end)], end)


def deepcopy_lists(outer, inner, populate=None):
    """Returns a list of lists with unique
    Python IDs for each outer list, populated with desired variable
    or callable object"""
    hold = []
    for i in range(outer):
        if callable(populate):
            hold.append([])
            for n in range(inner):
                hold[i].append(populate())
        elif not callable(populate):
            hold.append(deepcopy([populate] * inner))
    if outer == 1:
        hold = hold[0]
    return hold


def dict_flatten(*args):
    """flattens the given dictionary into a list"""
    hold = []
    for a in args:
        hold.append([i for s in a.values() for i in s])
    return hold


def check_binary(num, register):
    """Given a number and arduino register
    Return all corresponding arduino pins"""
    dicts = {'binary': 'pin_num'}
    if register == 'D':
        dicts = {1: 0, 2: 1, 4: 2, 8: 3,
                 16: 4, 32: 5, 64: 6, 128: 7}
    elif register == 'B':
        dicts = {1: 8, 2: 9, 4: 10,
                 8: 11, 16: 12, 32: 13}
    store = []
    for i in dicts:
        if num & i > 0:
            store.append(dicts[i])
    return store


#################################################################
# GUIs
class ScrollFrame(object):
    """Produces a scrollable canvas item"""

    def __init__(self, master, num_args, rows, bottom_padding=0):
        self.root = master
        self.rows = rows
        self.num_args = num_args
        self.bottom_padding = bottom_padding
        # Top Frame
        self.top_frame = Tk.Frame(self.root)
        self.top_frame.grid(row=0, column=0,
                            columnspan=self.num_args,
                            sticky=Tk.N + Tk.S + Tk.E + Tk.W)
        # Scroll Bar
        v_bar = Tk.Scrollbar(self.root, orient=Tk.VERTICAL)
        self.canvas = Tk.Canvas(self.root, yscrollcommand=v_bar.set)
        v_bar['command'] = self.canvas.yview
        self.canvas.bind_all('<MouseWheel>', self.on_vertical)
        v_bar.grid(row=1, column=self.num_args, sticky=Tk.N + Tk.S)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        # Middle Frame
        self.middle_frame = Tk.Frame(self.canvas)
        # Bottom Frame
        self.bottom_frame = Tk.Frame(self.root)
        self.bottom_frame.grid(row=2, column=0, columnspan=self.num_args + 1)

    def on_vertical(self, event):
        """returns vertical position of scrollbar"""
        self.canvas.yview_scroll(-1 * event.delta, 'units')

    def finalize(self):
        """finishes scrollbar setup"""
        self.canvas.create_window(0, 0, anchor=Tk.NW, window=self.middle_frame)
        self.canvas.grid(row=1, column=0,
                         columnspan=self.num_args, sticky=Tk.N + Tk.S + Tk.E + Tk.W)
        self.canvas.configure(scrollregion=(0, 0, 0, self.rows * 28 + self.bottom_padding))


class ProgressBar(object):
    """Creates a dynamic progress bar"""

    def __init__(self, master, canvas, bar, time_gfx, ms_total_time):
        self.master = master
        self.canvas = canvas
        self.segment_size = (float(ms_total_time / 1000)) / 1000
        self.ms_total_time = ms_total_time
        self.bar = bar
        self.time_gfx = time_gfx
        self.running = False
        self.start_prog = None
        self.num_prog, self.num_time = 1, 1
        self.time_diff = 0

    def start(self):
        """Starts the progress bar"""
        if self.num_prog != 1:
            self.canvas.move(self.bar, -self.num_prog + 1, 0)
            if (-self.num_prog + 1 + 35) < 0:
                text_move = max(-self.num_prog + 1 + 35, -929)
                self.canvas.move(self.time_gfx, text_move, 0)
            self.num_prog, self.num_time = 1, 1
        self.start_prog = datetime.now()
        self.running = True
        self.advance()

    def advance(self):
        """Moves the progressbar one increment when necessary"""
        if self.running:
            now = datetime.now()
            self.time_diff = (now - self.start_prog).seconds + float(
                (now - self.start_prog).microseconds) / 1000000
            if self.time_diff / self.num_time >= 0.005:
                self.canvas.itemconfig(self.time_gfx,
                                       text='{}'.format(format_secs(self.time_diff, True)))
                self.num_time += 1
            if self.time_diff / self.num_prog >= self.segment_size:
                self.canvas.move(self.bar, 1, 0)
                if (self.num_prog > 35) and (self.num_prog < 965):
                    self.canvas.move(self.time_gfx, 1, 0)
                self.num_prog += 1
            self.canvas.update()
            if self.num_prog > 1000 or self.time_diff > float(self.ms_total_time / 1000):
                self.running = False
                return self.running
            self.master.after(10, self.advance)

    def stop(self):
        """Stops the progress bar"""
        self.running = False


# noinspection PyClassicStyleClass
class LiveGraph(Tk.Frame):
    """Live Graph Plotting"""

    def __init__(self, *args, **kwargs):
        # noinspection PyTypeChecker,PyCallByClass
        Tk.Frame.__init__(self, *args, **kwargs)
        self.line_canvas = Tk.Canvas(self, background='#EFEFEF', height=216, width=580)
        self.line_canvas.grid(column=1, row=0)
        self.line_canvas.grid_rowconfigure(0, weight=1, uniform='x')
        self.label_canvas = Tk.Canvas(self, background='#EFEFEF', height=216, width=20)
        self.label_canvas.grid(column=0, row=0)
        self.label_canvas.grid_rowconfigure(1, weight=1, uniform='x')
        # color scheme
        self.color_scheme = ['#5da5da', '#faa43a', '#60bd68', '#f17cb0',
                             '#b2912f', '#b276b2', '#decf3f', '#f15854']
        self.lines = None
        self.line_labels = None
        self.create_new_lines()

    def create_new_lines(self):
        """creates 8 lines, corresponding to the 8 max channels on
        labjack"""
        self.lines = []
        self.line_labels = []
        lj_ch_num = deepcopy(dirs.settings.lj_last_used['ch_num'])
        lj_ch_num = lj_ch_num[::-1]
        for i in range(8):
            self.lines.append(self.line_canvas.create_line(0, 0, 0, 0, fill=self.color_scheme[i]))
        reverse_colors = (deepcopy(self.color_scheme)[:len(lj_ch_num)])[::-1]
        for i in range(len(lj_ch_num)):
            self.line_labels.append(self.label_canvas.create_text(1, 27 * i + 8, anchor=Tk.NW,
                                                                  fill=reverse_colors[i],
                                                                  text='{:0>2}'.format(lj_ch_num[i]),
                                                                  font=tkFont.Font(family='Arial', size=7)))

    def clear_plot(self):
        """clears existing lines on the graph"""
        for i in range(8):
            self.line_canvas.delete(self.lines[i])
        for i in self.line_labels:
            self.label_canvas.delete(i)

    def update_plot(self, *args):
        """Updates data on the plot"""
        for i in range(len(args[0])):
            self.add_point(self.lines[i], args[0][i])
        self.line_canvas.xview_moveto(1.0)

    def add_point(self, line, y):
        """adds new data to existing plot"""
        coords = self.line_canvas.coords(line)
        x = coords[-2] + 1
        coords.append(x)
        coords.append(y)
        coords = coords[:]  # keep # of points to a manageable size
        self.line_canvas.coords(line, *coords)
        self.line_canvas.configure(scrollregion=self.line_canvas.bbox("all"))


# noinspection PyClassicStyleClass,PyTypeChecker
class SimpleTable(object, Tk.Frame):
    """Creates a table with defined rows and columns
    modifiable via a set command"""
    # noinspection PyCallByClass
    def __init__(self, master, rows, columns, highlight_column, highlight_color):
        Tk.Frame.__init__(self, master, background="black")
        self.text_var = deepcopy_lists(rows, columns, Tk.StringVar)
        for row in range(rows):
            for column in range(columns):
                if column == highlight_column:
                    label = Tk.Label(self, textvariable=self.text_var[row][column],
                                     borderwidth=0, width=10, height=1,
                                     font=tkFont.Font(root=master, family='Arial', size=8),
                                     bg=highlight_color)
                else:
                    label = Tk.Label(self, textvariable=self.text_var[row][column],
                                     borderwidth=0, width=10, height=1,
                                     font=tkFont.Font(root=master, family='Helvetica', size=8))
                label.grid(row=row, column=column, sticky='nsew', padx=1, pady=1)
                self.text_var[row][column].set('')
        for column in range(columns):
            self.grid_columnconfigure(column, weight=1)

    def set_var(self, row, column, value):
        """sets a specific box to specified value"""
        item = self.text_var[row][column]
        item.set(value)

    def clear(self):
        """clears fields"""
        for row in range(len(self.text_var) - 1):
            for column in range(len(self.text_var[row]) - 1):
                self.text_var[row + 1][column + 1].set('')


class GUI(object):
    """Standard TKinter GUI"""

    def __init__(self, tcl_root, topmost=True):
        self.root = tcl_root
        self.root.resizable(width=False, height=False)
        self.ALL = Tk.N + Tk.E + Tk.S + Tk.W
        self.root.protocol('WM_DELETE_WINDOW', self.hard_exit)
        self.hard_closed = False
        if topmost:
            self.root.wm_attributes("-topmost", True)
        self.root.focus_force()

    def hard_exit(self):
        """Destroy all instances of the window
        if close button is pressed
        Prevents ID errors and clashes"""
        self.hard_closed = True
        self.root.destroy()
        self.root.quit()

    def center(self):
        """Centers GUI window"""
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        [window_width, window_height] = list(
            int(i) for i in
            self.root.geometry().split('+')[0].split('x'))
        x_pos = screen_width / 2 - window_width / 2
        y_pos = screen_height / 2 - window_height / 2
        self.root.geometry('{}x{}+{}+{}'.format(
            window_width,
            window_height,
            x_pos, y_pos))

    def run(self):
        """Initiate GUI"""
        self.center()
        self.root.mainloop()

    def platform_geometry(self, windows, darwin):
        """Changes window dimensions based on platform"""
        if sys.platform.startswith('win'):
            self.root.geometry(windows)
        elif sys.platform.startswith('darwin'):
            self.root.geometry(darwin)
        else:
            pass


class PhotometryGUI(GUI):
    """GUI for Configuring Photometry Options
    *Does not affect actual program function
        - When saving file outputs, photometry config options
          are appended to aid in Lock-In Analysis
    Options appended: - Channels Used and associated Data column
                      - Sample stimulation frequencies (primary and isosbestic)"""

    def __init__(self, master):
        GUI.__init__(self, master)
        self.root.title('Photometry Configuration')
        # Grab last used settings
        self.ch_num = dirs.settings.fp_last_used['ch_num']
        self.stim_freq = {'main': dirs.settings.fp_last_used['main_freq'],
                          'isos': dirs.settings.fp_last_used['isos_freq']}
        # Variables
        self.radio_button_vars = deepcopy_lists(outer=1, inner=3,
                                                populate=Tk.IntVar)
        self.label_names = ['Photometry Data Channel',
                            'Main Reference Channel',
                            'Isosbestic Reference Channel']
        self.main_entry = None
        self.isos_entry = None
        # Setup GUI
        self.setup_radio_buttons()
        self.setup_entry_fields()
        Tk.Button(self.root, text='FINISH', command=self.exit).pack(side=Tk.BOTTOM)

    def setup_radio_buttons(self):
        """sets up radio buttons for LabJack channel selection"""
        for i in range(3):
            self.radio_button_vars[i].set(self.ch_num[i])
        Tk.Label(self.root,
                 text='\nPrevious Settings Loaded\n'
                      'These settings will be saved in your .csv outputs.\n',
                 relief=Tk.RAISED).pack(fill='both', expand='yes')
        data_frame = Tk.LabelFrame(self.root,
                                   text=self.label_names[0])
        true_frame = Tk.LabelFrame(self.root,
                                   text=self.label_names[1])
        isos_frame = Tk.LabelFrame(self.root,
                                   text=self.label_names[2])
        frames = [data_frame, true_frame, isos_frame]
        buttons = deepcopy_lists(outer=3, inner=14)
        for frame in range(3):
            frames[frame].pack(fill='both', expand='yes')
            for i in range(14):
                buttons[frame][i] = Tk.Radiobutton(frames[frame],
                                                   text=str(i), value=i,
                                                   variable=self.radio_button_vars[frame],
                                                   command=lambda (button_var,
                                                                   index)=(self.radio_button_vars[frame],
                                                                           frame):
                                                   self.select_button(button_var, index))
                buttons[frame][i].pack(side=Tk.LEFT)

    def setup_entry_fields(self):
        """sets up entry fields for frequency entries"""
        freq_frame = Tk.LabelFrame(self.root,
                                   text='Primary and Isosbestic '
                                        'Stimulation Frequencies')
        freq_frame.pack(fill='both', expand='yes')
        Tk.Label(freq_frame, text='Main Frequency: ').pack(side=Tk.LEFT)
        self.main_entry = Tk.Entry(freq_frame)
        self.main_entry.pack(side=Tk.LEFT)
        self.isos_entry = Tk.Entry(freq_frame)
        self.isos_entry.pack(side=Tk.RIGHT)
        Tk.Label(freq_frame, text='Isosbestic Frequency: ').pack(side=Tk.RIGHT)
        self.main_entry.insert(Tk.END, '{}'.format(str(self.stim_freq['main'])))
        self.isos_entry.insert(Tk.END, '{}'.format(str(self.stim_freq['isos'])))

    def select_button(self, var, ind):
        """Changes button variables when user selects an option"""
        if var.get() not in self.ch_num:
            self.ch_num[ind] = var.get()
        else:
            temp_report = self.label_names[self.ch_num.index(var.get())]
            tkMb.showinfo('Error!',
                          'You already selected \n['
                          'Channel {}] \n'
                          'for \n'
                          '[{}]!'.format(var.get(), temp_report),
                          parent=self.root)
            self.radio_button_vars[ind].set(self.ch_num[ind])

    def exit(self):
        """Quit Photometry"""
        try:
            true_freq = int(self.main_entry.get().strip())
            isos_freq = int(self.isos_entry.get().strip())
            if true_freq == 0 or isos_freq == 0:
                tkMb.showinfo('Error!', 'Stimulation Frequencies '
                                        'must be higher than 0 Hz!',
                              parent=self.root)
            elif true_freq == isos_freq:
                tkMb.showinfo('Error!', 'Main sample and Isosbestic Frequencies '
                                        'should not be the same value.',
                              parent=self.root)
            else:
                self.stim_freq = {'main': true_freq,
                                  'isos': isos_freq}
                to_save = {'ch_num': self.ch_num,
                           'main_freq': self.stim_freq['main'],
                           'isos_freq': self.stim_freq['isos']}
                dirs.threadsafe_edit(recipient='fp_last_used', donor=to_save)
                self.root.destroy()
                self.root.quit()
        except ValueError:
            tkMb.showinfo('Error!', 'Stimulation frequencies must be '
                                    'Integers in Hz.',
                          parent=self.root)


class LabJackGUI(GUI):
    """GUI for LabJack configuration"""

    def __init__(self, master):
        GUI.__init__(self, master)
        self.root.title('LabJack Configuration')
        self.lj_save_name = ''
        # Grab last used LJ settings
        self.ch_num = dirs.settings.lj_last_used['ch_num']
        self.scan_freq = dirs.settings.lj_last_used['scan_freq']
        self.n_ch = len(self.ch_num)
        # Variables
        self.preset_list = []
        self.preset_chosen = Tk.StringVar()
        self.preset_menu = None
        self.new_save_entry = None
        self.button_vars = deepcopy_lists(outer=1, inner=14,
                                          populate=Tk.IntVar)
        self.scan_entry = None
        # Setup GUI
        self.preset_gui()
        self.manual_config_gui()
        Tk.Button(self.root,
                  text='FINISH',
                  command=self.exit).grid(row=1, column=0, columnspan=2)

    def update_preset_list(self):
        """Updates self.preset_list with all available presets"""
        self.preset_list = [i for i in dirs.settings.lj_presets]

    def preset_gui(self):
        """Loads all presets into a menu for selection"""
        self.update_preset_list()
        # Create frame
        right_frame = Tk.LabelFrame(self.root, text='Preset Configuration')
        right_frame.grid(row=0, column=1)
        # Load Presets
        Tk.Label(right_frame, text='\nChoose a Preset'
                                   '\nOr Save a '
                                   'New Preset:').pack(fill='both',
                                                       expand='yes')
        # existing presets
        preset_frame = Tk.LabelFrame(right_frame, text='Select a Saved Preset')
        preset_frame.pack(fill='both', expand='yes')
        self.preset_chosen.set(max(self.preset_list, key=len))
        self.preset_menu = Tk.OptionMenu(preset_frame, self.preset_chosen,
                                         *self.preset_list,
                                         command=self.preset_list_choose)
        self.preset_menu.config(width=10)
        self.preset_menu.pack(side=Tk.TOP)
        # Save New Presets
        new_preset_frame = Tk.LabelFrame(right_frame, text='(Optional): '
                                                           'Save New Preset')
        new_preset_frame.pack(fill='both', expand='yes')
        self.new_save_entry = Tk.Entry(new_preset_frame)
        self.new_save_entry.pack()
        Tk.Button(new_preset_frame, text='SAVE',
                  command=self.preset_save).pack()

    def preset_list_choose(self, name):
        """Configures settings based on preset chosen"""
        self.preset_chosen.set(name)
        self.ch_num = dirs.settings.lj_presets[name]['ch_num']
        self.scan_freq = dirs.settings.lj_presets[name]['scan_freq']
        self.n_ch = len(self.ch_num)
        # Clear settings and set to preset config
        for i in range(14):
            self.button_vars[i].set(0)
        for i in self.ch_num:
            self.button_vars[i].set(1)
        self.scan_entry.delete(0, Tk.END)
        self.scan_entry.insert(Tk.END, self.scan_freq)

    def preset_save(self):
        """Saves settings to new preset if settings are valid"""
        self.update_preset_list()
        validity = self.check_input_validity()
        if validity:
            save_name = self.new_save_entry.get().strip().lower()
            if len(save_name) == 0:
                tkMb.showinfo('Error!',
                              'You must give your Preset a name.',
                              parent=self.root)
            elif len(save_name) != 0:
                if save_name not in dirs.settings.lj_presets:
                    to_save = {'ch_num': self.ch_num, 'scan_freq': self.scan_freq}
                    dirs.threadsafe_edit(recipient='lj_presets', name=save_name,
                                         donor=to_save)
                    tkMb.showinfo('Saved!', 'Preset saved as '
                                            '[{}]'.format(save_name),
                                  parent=self.root)
                    menu = self.preset_menu.children['menu']
                    menu.add_command(label=save_name,
                                     command=lambda:
                                     self.preset_list_choose(save_name))
                    self.preset_chosen.set(save_name)
                elif save_name in dirs.settings.lj_presets:
                    if tkMb.askyesno('Overwrite?',
                                     '[{}] already exists.\n'
                                     'Overwrite this preset?'.format(save_name),
                                     parent=self.root):
                        to_save = {'ch_num': self.ch_num, 'scan_freq': self.scan_freq}
                        dirs.threadsafe_edit(recipient='lj_presets', name=save_name,
                                             donor=to_save)
                        tkMb.showinfo('Saved!', 'Preset saved as '
                                                '[{}]'.format(save_name),
                                      parent=self.root)

    def manual_config_gui(self):
        """Manually configure LabJack settings"""
        left_frame = Tk.LabelFrame(self.root, text='Manual Configuration')
        left_frame.grid(row=0, column=0)
        Tk.Label(left_frame, text='\nMost Recently '
                                  'Used Settings:').pack(fill='both',
                                                         expand='yes')
        # Configure channels
        ch_frame = Tk.LabelFrame(left_frame, text='Channels Selected')
        ch_frame.pack(fill='both', expand='yes')
        # Create Check Buttons
        buttons = deepcopy_lists(outer=1, inner=14)
        for i in range(14):
            buttons[i] = Tk.Checkbutton(ch_frame, text='{:0>2}'.format(i),
                                        variable=self.button_vars[i],
                                        onvalue=1, offvalue=0,
                                        command=self.select_channel)
        for i in range(14):
            buttons[i].grid(row=i // 5, column=i - (i // 5) * 5)
        for i in self.ch_num:
            buttons[i].select()
        # Configure sampling frequency
        scan_frame = Tk.LabelFrame(left_frame, text='Scan Frequency')
        scan_frame.pack(fill='both', expand='yes')
        Tk.Label(scan_frame, text='Freq/Channel (Hz):').pack(side=Tk.LEFT)
        self.scan_entry = Tk.Entry(scan_frame, width=8)
        self.scan_entry.pack(side=Tk.LEFT)
        self.scan_entry.insert(Tk.END, self.scan_freq)

    def select_channel(self):
        """Configures check buttons for LJ channels based
        on user selection"""
        redo = False
        temp_ch_num = deepcopy(self.ch_num)
        self.ch_num = []
        for i in range(14):
            if self.button_vars[i].get() == 1:
                self.ch_num.append(i)
        self.n_ch = len(self.ch_num)
        if self.n_ch > 8:
            tkMb.showinfo('Error!',
                          'You cannot use more than 8 LabJack '
                          'Channels at once.',
                          parent=self.root)
            redo = True
        elif self.n_ch == 0:
            tkMb.showinfo('Error!',
                          'You must configure at least one '
                          'Channel.',
                          parent=self.root)
            redo = True
        if redo:
            self.ch_num = temp_ch_num
            for i in range(14):
                self.button_vars[i].set(0)
            for i in self.ch_num:
                self.button_vars[i].set(1)
            self.n_ch = len(self.ch_num)

    def check_input_validity(self):
        """Checks if user inputs are valid;
        if valid, saves to settings object"""
        validity = False
        button_state = []
        for i in self.button_vars:
            button_state.append(i.get())
        if 1 not in button_state:
            tkMb.showinfo('Error!',
                          'You must pick at least one LabJack '
                          'Channel to Record from.',
                          parent=self.root)
        else:
            try:
                self.scan_freq = int(self.scan_entry.get().strip())
                max_freq = int(50000 / self.n_ch)
                if self.scan_freq == 0:
                    tkMb.showinfo('Error!',
                                  'Scan Frequency must be higher than 0 Hz.',
                                  parent=self.root)
                elif self.scan_freq > max_freq:
                    tkMb.showinfo('Error!',
                                  'SCAN FREQUENCY x NUMBER OF CHANNELS \n'
                                  'must be lower than [50,000Hz]\n\n'
                                  'Max [{} Hz] right now with [{}] Channels '
                                  'in use.'.format(max_freq, self.n_ch),
                                  parent=self.root)
                else:
                    validity = True
                    to_save = {'ch_num': self.ch_num, 'scan_freq': self.scan_freq}
                    dirs.threadsafe_edit(recipient='lj_last_used', donor=to_save)
            except ValueError:
                tkMb.showinfo('Error!', 'Scan Frequency must be an '
                                        'Integer in Hz.',
                              parent=self.root)
        return validity

    def exit(self):
        """Validates inputs and closes GUI"""
        validity = self.check_input_validity()
        if validity:
            self.root.destroy()
            self.root.quit()


class ArduinoGUI(GUI):
    """Arduino settings config. Settings are saved to
    dirs.settings object, which is pulled by the arduino at
    experiment start"""

    def __init__(self, master):
        GUI.__init__(self, master)
        self.types = ''
        self.num_entries = 0
        # Variables
        self.output_ids, self.pwm_ids = (range(2, 8), range(8, 14))
        self.pwm_ids.remove(10)
        self.pin_button_vars = None
        self.entries = None
        self.closebutton = None
        # Default entry validating does not end in closing the GUI
        self.close_gui = False
        # Pull last used settings
        [self.packet, self.tone_pack,
         self.out_pack, self.pwm_pack] = dirs.settings.quick_ard()
        self.max_time = 0
        self.data = {'starts': {}, 'middles': {}, 'ends': {}, 'hold': {}}
        self.return_data = []
        self.fields_validated = {}

    def tone_setup(self):
        """Tone GUI"""
        self.root.title('Tone Configuration')
        self.types = 'tone'
        num_pins, self.num_entries = 1, 15
        scroll_frame = ScrollFrame(self.root, num_args=num_pins,
                                   rows=self.num_entries + 1)
        # Setup Toggle Buttons
        self.pin_button_vars = Tk.IntVar()
        self.pin_button_vars.set(0)
        pin_button = Tk.Checkbutton(scroll_frame.top_frame,
                                    text='Enable Tone\n'
                                         '(Arduino Pin 10)',
                                    variable=self.pin_button_vars,
                                    onvalue=1, offvalue=0,
                                    command=lambda: self.button_toggle('tone'))
        pin_button.pack()
        # Setup Entries
        self.entries = [None] * self.num_entries
        Tk.Label(scroll_frame.middle_frame,
                 text='Time On(s), '
                      'Time until Off(s), '
                      'Freq (Hz)').grid(row=0, column=1, sticky=self.ALL)
        for row in range(self.num_entries):
            Tk.Label(scroll_frame.middle_frame,
                     text='{:0>2}'.format(row + 1)).grid(row=row + 1, column=0)
            validate = (scroll_frame.middle_frame.register(self.entry_validate),
                        False, row)
            self.entries[row] = Tk.Entry(scroll_frame.middle_frame,
                                         validate='focusout',
                                         validatecommand=validate)
            self.entries[row].grid(row=row + 1, column=1, sticky=self.ALL)
            self.entries[row].config(state=Tk.DISABLED)
        # Confirm button
        self.closebutton = Tk.Button(scroll_frame.bottom_frame,
                                     text='CONFIRM',
                                     command=self.pre_close)
        self.closebutton.pack(side=Tk.TOP)
        scroll_frame.finalize()
        # Finish setup
        self.platform_geometry(windows='308x420', darwin='257x272')

    def pwm_setup(self):
        """PWM Config"""
        self.root.title('PWM Configuration')
        self.types = 'pwm'
        num_pins, self.num_entries = 5, 15
        scroll_frame = ScrollFrame(self.root, num_pins,
                                   self.num_entries + 1, bottom_padding=50)
        # Usage instructions
        info_frame = Tk.LabelFrame(scroll_frame.top_frame,
                                   text='Enable Arduino Pins')
        info_frame.grid(row=0, column=0, sticky=self.ALL)
        Tk.Label(info_frame, text=' ' * 2).pack(side=Tk.RIGHT)
        Tk.Label(info_frame, text='e.g. 0,180,200,20,90  (Per Field)',
                 relief=Tk.RAISED).pack(side=Tk.RIGHT)
        Tk.Label(info_frame, text=' ' * 2).pack(side=Tk.RIGHT)
        Tk.Label(info_frame,
                 text='Enable pins, then input instructions '
                      'with comma separation.',
                 relief=Tk.RAISED).pack(side=Tk.RIGHT)
        Tk.Label(info_frame,
                 text=' ' * 5).pack(side=Tk.RIGHT)
        # Variables
        self.entries = deepcopy_lists(outer=num_pins, inner=self.num_entries)
        self.pin_button_vars = deepcopy_lists(outer=1, inner=num_pins,
                                              populate=Tk.IntVar)
        pin_buttons = [None] * num_pins
        # Setup items
        for pin in range(num_pins):
            pin_buttons[pin] = Tk.Checkbutton(info_frame,
                                              text='Pin {:0>2}'.format(self.pwm_ids[pin]),
                                              variable=self.pin_button_vars[pin],
                                              onvalue=1, offvalue=0,
                                              command=lambda tags=self.pwm_ids[pin]:
                                              self.button_toggle(tags))
            pin_buttons[pin].pack(side=Tk.LEFT)
            Tk.Label(scroll_frame.middle_frame,
                     text='Pin {:0>2}\n'
                          'Time On(s), '
                          'Time until Off(s), \n'
                          'Freq (Hz), '
                          'Duty Cycle (%),\n'
                          'Phase Shift '.format(self.pwm_ids[pin]) + '(' + u'\u00b0' + ')').grid(row=0, column=1 + pin)
            for row in range(self.num_entries):
                validate = (scroll_frame.middle_frame.register(self.entry_validate),
                            pin, row)
                Tk.Label(scroll_frame.middle_frame,
                         text='{:0>2}'.format(row + 1)).grid(row=row + 1, column=0)
                self.entries[pin][row] = Tk.Entry(scroll_frame.middle_frame, width=25,
                                                  validate='focusout',
                                                  validatecommand=validate)
                self.entries[pin][row].grid(
                    row=row + 1, column=1 + pin)
                self.entries[pin][row].config(state='disabled')
        # Confirm Button
        self.closebutton = Tk.Button(scroll_frame.bottom_frame,
                                     text='CONFIRM',
                                     command=self.pre_close)
        self.closebutton.pack(side=Tk.TOP)
        scroll_frame.finalize()
        # Finish Setup
        self.platform_geometry(windows='1070x440', darwin='1100x280')

    def output_setup(self):
        """Output GUI"""
        self.root.title('Simple Output Configuration')
        self.types = 'output'
        num_pins, self.num_entries = 6, 15
        scroll_frame = ScrollFrame(self.root, num_pins, self.num_entries + 1,
                                   bottom_padding=8)
        # Usage instructions
        info_frame = Tk.LabelFrame(scroll_frame.top_frame,
                                   text='Enable Arduino Pins')
        info_frame.grid(row=0, column=0, sticky=self.ALL)
        Tk.Label(info_frame, text=' ' * 21).pack(side=Tk.RIGHT)
        Tk.Label(info_frame, text='Enable pins, then input instructions '
                                  'line by line with comma '
                                  'separation.',
                 relief=Tk.RAISED).pack(side=Tk.RIGHT)
        Tk.Label(info_frame, text=' ' * 21).pack(side=Tk.RIGHT)
        # Variables
        self.entries = deepcopy_lists(outer=num_pins, inner=self.num_entries)
        self.pin_button_vars = deepcopy_lists(outer=1, inner=num_pins,
                                              populate=Tk.IntVar)
        pin_buttons = [None] * num_pins
        # Setup items
        for pin in range(num_pins):
            pin_buttons[pin] = Tk.Checkbutton(info_frame,
                                              text='PIN {:0>2}'.format(
                                                  self.output_ids[pin]),
                                              variable=self.pin_button_vars[pin],
                                              onvalue=1, offvalue=0,
                                              command=lambda tags=self.output_ids[pin]:
                                              self.button_toggle(tags))
            pin_buttons[pin].pack(side=Tk.LEFT)
            Tk.Label(scroll_frame.middle_frame,
                     text='Pin {:0>2}\n'
                          'Time On(s), '
                          'Time until Off(s)'.format(self.output_ids[pin])).grid(row=0,
                                                                                 column=1 + pin)
            for row in range(self.num_entries):
                validate = (scroll_frame.middle_frame.register(self.entry_validate),
                            pin, row)
                Tk.Label(scroll_frame.middle_frame,
                         text='{:0>2}'.format(row + 1)).grid(row=row + 1, column=0)
                self.entries[pin][row] = Tk.Entry(scroll_frame.middle_frame, width=18,
                                                  validate='focusout',
                                                  validatecommand=validate)
                self.entries[pin][row].grid(row=row + 1, column=1 + pin)
                self.entries[pin][row].config(state=Tk.DISABLED)
        # Confirm Button
        self.closebutton = Tk.Button(scroll_frame.bottom_frame,
                                     text='CONFIRM',
                                     command=self.pre_close)
        self.closebutton.pack(side=Tk.TOP)
        scroll_frame.finalize()
        # Finish Setup
        self.center()
        self.platform_geometry(windows='1198x430', darwin='1110x272')

    def button_toggle(self, tags):
        """Toggles the selected pin button"""
        if tags == 'tone':
            if self.pin_button_vars.get() == 0:
                for row in range(self.num_entries):
                    self.entries[row].configure(state=Tk.DISABLED)
            elif self.pin_button_vars.get() == 1:
                for row in range(self.num_entries):
                    self.entries[row].configure(state=Tk.NORMAL)
        else:
            var, ind = None, None
            if tags in self.output_ids:
                ind = self.output_ids.index(tags)
                var = self.pin_button_vars[ind]
            elif tags in self.pwm_ids:
                ind = self.pwm_ids.index(tags)
                var = self.pin_button_vars[ind]
            if var.get() == 0:
                for entry in range(self.num_entries):
                    self.entries[ind][entry].configure(state=Tk.DISABLED)
            elif var.get() == 1:
                for entry in range(self.num_entries):
                    self.entries[ind][entry].configure(state=Tk.NORMAL)

    # noinspection PyTypeChecker
    def entry_validate(self, pins=False, rows=None):
        """Checks inputs are valid"""
        entry, err_place_msg, arg_types = None, '', []
        row = int(rows)
        pin = None
        if pins:
            pin = int(pins)
        # If we request a close via confirm button, we do a final check
        close_gui = self.close_gui
        if self.close_gui:
            # set to False so if check fails we don't get stuck in a loop
            self.close_gui = False
        pin_ids = 0
        ####################################################################
        if self.types == 'tone':
            pin_ids = 10
            entry = self.entries[row]
            arg_types = ['Time On (s)', 'Time until Off (s)', 'Frequency (Hz)']
            err_place_msg = 'row [{:0>2}]'.format(row + 1)
        elif self.types == 'output':
            pin_ids = self.output_ids[pin]
            entry = self.entries[pin][row]
            arg_types = ['Time On (s)', 'Time until Off (s)']
            err_place_msg = 'row [{:0>2}], pin [{:0>2}]'.format(row + 1, pin_ids)
        elif self.types == 'pwm':
            pin_ids = self.pwm_ids[pin]
            entry = self.entries[pin][row]
            arg_types = ['Time On (s)', 'Time until Off (s)', 'Frequency (Hz)',
                         'Duty Cycle (%)', 'Phase Shift (deg)']
            err_place_msg = 'row [{:0>2}], pin [{:0>2}]'.format(row + 1, pin_ids)
        ####################################################################
        # Grab comma separated user inputs as a list
        inputs = entry.get().strip().split(',')
        for i in range(len(inputs)):
            inputs[i] = inputs[i].strip()
        # Now we begin to check entry validity
        # 1. Check Commas don't occur at ends or there exist any double commas:
        while True:
            time.sleep(0.0001)
            if '' in inputs:
                inputs.pop(inputs.index(''))
            else:
                break
        # 2. Check we have correct number of input arguments
        num_args = len(arg_types)
        error_str = ''
        for i in range(num_args):
            if i == 3:
                error_str += '\n'
            error_str += str(arg_types[i])
            if i < num_args - 1:
                error_str += ', '
        # 2a. More than 0 but not num_args
        if len(inputs) != num_args and len(inputs) > 0:
            tkMb.showinfo('Error!',
                          'Error in {}:\n'
                          'Setup requires [{}] arguments for each entry.\n\n'
                          'Comma separated in this order:\n\n'
                          '[{}]'.format(err_place_msg, num_args, error_str),
                          parent=self.root)
            entry.focus()
            return False
        # 2b. Exactly 0: we don't need to process an empty field
        if len(inputs) == 0:
            if close_gui:
                self.close()
            return False
        # 3. Check input content are valid
        try:
            on, off = int(inputs[0]), int(inputs[1])
            on_ms, off_ms = on * 1000, off * 1000
            refr, freq, phase, duty_cycle = None, 0, 0, 0
            if self.types == 'tone':
                freq = int(inputs[2])
                refr = freq
            elif self.types == 'output':
                refr = pin_ids
            elif self.types == 'pwm':
                freq = int(inputs[2])
                duty_cycle = int(inputs[3])
                phase = int(inputs[4])
                refr = long('{:0>5}{:0>5}{:0>5}'.format(freq, duty_cycle, phase))
            # 3a. Store max time configured; at close, if max_time > dirs.settings max time,
            #     we change the max time for procedure
            if (on_ms + off_ms) > self.max_time and off_ms != 0:
                self.max_time = on_ms + off_ms
            # 3b. Time interval for each entry must be > 0
            if off == 0:
                tkMb.showinfo('Error!',
                              'Error in {}:\n\n'
                              'Time Interval (i.e. '
                              'Time until Off) '
                              'cannot be 0s!'.format(err_place_msg),
                              parent=self.root)
                entry.focus()
                return False
            # 3c. Type specific checks
            if self.types == 'tone':
                if freq < 50:
                    tkMb.showinfo('Error!',
                                  'Error in {}:\n\n'
                                  'The TONE function works '
                                  'best for high frequencies.\n\n'
                                  'Use the PWM function '
                                  'instead for low Hz '
                                  'frequency modulation'.format(err_place_msg),
                                  parent=self.root)
                    entry.focus()
                    return False
            if self.types == 'pwm':
                if phase not in range(361):
                    tkMb.showinfo('Error!',
                                  'Error in {}:\n\n'
                                  'Phase Shift must be an integer\n'
                                  'between 0 and 360 degrees.'.format(err_place_msg),
                                  parent=self.root)
                    entry.focus()
                    return False
                if duty_cycle not in range(1, 100):
                    tkMb.showinfo('Error!',
                                  'Error in {}:\n\n'
                                  'Duty Cycle must '
                                  'be an integer '
                                  'percentage between '
                                  '1 and 99 inclusive.'.format(err_place_msg),
                                  parent=self.root)
                    entry.focus()
                    return False
                if freq > 100:
                    tkMb.showinfo('Error!',
                                  'Error in {}:\n\n'
                                  'The PWM function works best'
                                  'for frequencies <= 100 Hz.\n\n'
                                  'Use the TONE function or an'
                                  'external wave '
                                  'generator instead.'.format(err_place_msg),
                                  parent=self.root)
                    entry.focus()
                    return False
        except ValueError:
            tkMb.showinfo('Error!',
                          'Error in {}:\n\n'
                          'Input arguments '
                          'must be comma '
                          'separated integers'.format(err_place_msg),
                          parent=self.root)
            entry.focus()
            return False
        # 4. Check if any time intervals overlap
        #       Rules:
        #       - Time intervals cannot overlap for the same pin
        #       - Time intervals next to each other
        #         at the same [refr] will be joined into a single segment
        #         to save space on arduino
        #       Therefore:
        #       - OUTPUT Pins can always overlap. We just need to combine the time inputs
        #       - PWM Pins can overlap iff same [refr]; else raise error
        #       - Tone is one pin only. Only overlap if same [freq]
        #       (to date only implemented joining adjacent segments; no overlap
        #        managing available)
        ################################################################################
        # ...because pwm is a special butterfly and needs extra steps:
        starts_l, middles_l, ends_l, hold_l = {}, {}, {}, {}
        if self.types == 'pwm':
            pin_int = self.pin_to_int(pin_ids)
            # temporarily hold in starts_l so we can use self.data in the same way
            # for pwm and output/tone in the following
            (starts_l, middles_l, ends_l, hold_l) = (self.data['starts'],
                                                     self.data['middles'],
                                                     self.data['ends'],
                                                     self.data['hold'])
            try:
                starts_l[pin_ids], middles_l[pin_ids], ends_l[pin_ids], hold_l[pin_int]
            except KeyError:
                (starts_l[pin_ids], middles_l[pin_ids],
                 ends_l[pin_ids], hold_l[pin_int]) = {}, {}, {}, {}
            (self.data['starts'], self.data['middles'],
             self.data['ends'], self.data['hold']) = (starts_l[pin_ids], middles_l[pin_ids],
                                                      ends_l[pin_ids], hold_l[pin_int])
        # 4a.
        # Before we validate entries further:
        # If the validation is performed on a field that already had data validated
        # e.g. because user misclicked or needs to edit
        # we will need to remove its previous set of data first to prevent clashing
        self.time_remove(rows, pins, refr)
        # 4b. test for time overlaps
        starts_all, ends_all, middles_all = [], [], []
        try:
            self.data['starts'][refr], self.data['middles'][refr], self.data['ends'][refr]
        except KeyError:
            self.data['starts'][refr], self.data['middles'][refr], self.data['ends'][refr] = [], [], []
        if self.types in ['tone', 'pwm']:
            try:
                self.data['hold'][refr]
            except KeyError:
                self.data['hold'][refr] = []
            (starts_all, middles_all, ends_all) = dict_flatten(self.data['starts'],
                                                               self.data['middles'],
                                                               self.data['ends'])
        elif self.types == 'output':
            (starts_all, middles_all, ends_all) = (self.data['starts'][pin_ids],
                                                   self.data['middles'][pin_ids],
                                                   self.data['ends'][pin_ids])
        if on in starts_all or on + off in ends_all or on in middles_all or on + off in middles_all:
            tkMb.showinfo('Error!', 'Error in {}:\n\n'
                                    'Time intervals '
                                    'should not overlap for the same '
                                    'pin!'.format(err_place_msg),
                          parent=self.root)
            entry.focus()
            return False
        # 4c. We've finished checking for validity.
        #     If the input reached this far, it's ready to be added
        self.data['middles'][refr] += range(on + 1, on + off)
        front, back = 0, 0
        self.time_combine(on_ms, off_ms, front, back, refr)
        if on in self.data['ends'][refr] and on + off not in self.data['starts'][refr]:
            front, back = 1, 0
            self.data['middles'][refr].append(on)
            self.data['ends'][refr].remove(on)
            self.data['ends'][refr].append(on + off)
            self.time_combine(on_ms, off_ms, front, back, refr)
        elif on not in self.data['ends'][refr] and on + off in self.data['starts'][refr]:
            front, back = 0, 1
            self.data['middles'][refr].append(on + off)
            self.data['starts'][refr].remove(on + off)
            self.data['starts'][refr].append(on)
            self.time_combine(on_ms, off_ms, front, back, refr)
        elif on in self.data['ends'][refr] and on + off in self.data['starts'][refr]:
            front, back = 1, 1
            self.data['middles'][refr].append(on)
            self.data['middles'][refr].append(on + off)
            self.data['starts'][refr].remove(on + off)
            self.data['ends'][refr].remove(on)
            self.time_combine(on_ms, off_ms, front, back, refr)
        else:
            self.data['starts'][refr].append(on)
            self.data['ends'][refr].append(on + off)
        # Now we need to make sure this one comes out as an already validated field
        if self.types == 'tone':
            self.fields_validated[rows] = {'starts': on,
                                           'middles': range(on + 1, on + off),
                                           'ends': on + off,
                                           'hold': [on_ms, on_ms + off_ms],
                                           'refr': refr}
        elif self.types == 'output':
            pin_int = self.pin_to_int(refr)
            self.fields_validated[rows + pins] = {'starts': on,
                                                  'middles': range(on + 1, on + off),
                                                  'ends': on + off,
                                                  'hold': {on_ms: pin_int, off_ms: pin_int},
                                                  'refr': refr}
        elif self.types == 'pwm':
            self.fields_validated[rows + pins] = {'starts': on,
                                                  'middles': range(on + 1, on + off),
                                                  'ends': on + off,
                                                  'hold': [on_ms, on_ms + off_ms],
                                                  'refr': refr}
        # again, pwm requires some extra work before we finish...
        if self.types == 'pwm':
            (self.data['starts'],
             self.data['middles'],
             self.data['ends'],
             self.data['hold']) = (starts_l, middles_l, ends_l, hold_l)
        # If all is well and we requested a close, we close the GUI
        if close_gui:
            self.close()
        else:
            return True

    @staticmethod
    def pin_to_int(pin):
        """Returns the integer representation of
        any given arduino pin"""
        if pin < 8:
            return int('1' + '0' * int(pin), 2)
        if 8 <= pin <= 13:
            return int('1' + '0' * (int(pin) - 8), 2)

    # noinspection PyStatementEffect,PyUnresolvedReferences,PyTypeChecker
    def time_remove(self, rows, pins, refr):
        """Removes the indicated time segment"""
        field = {}
        if self.types == 'tone':
            try:
                self.fields_validated[rows]
            except KeyError:
                self.fields_validated[rows] = {'starts': -1, 'middles': [],
                                               'ends': -1, 'hold': [], 'refr': refr}
                return
            field = self.fields_validated[rows]
        elif self.types in ['output', 'pwm']:
            try:
                self.fields_validated[rows + pins]
            except KeyError:
                self.fields_validated[rows + pins] = {'starts': -1, 'middles': [],
                                                      'ends': -1, 'hold': [], 'refr': refr}
                return
            field = self.fields_validated[rows + pins]
        field_refr = field['refr']
        if self.types in ['tone', 'pwm']:
            try:
                # Check that the data exists at refr
                self.data['starts'][field_refr], self.data['middles'][field_refr]
                self.data['ends'][field_refr], self.data['hold'][field_refr]
                # Remove Middles
                for i in field['middles']:
                    if i in self.data['middles'][field_refr]:
                        self.data['middles'][field_refr].remove(i)
                # Remove starts, ends, holds
                if field['starts'] in self.data['starts'][field_refr]:
                    self.data['starts'][field_refr].remove(field['starts'])
                    self.data['hold'][field_refr].remove(field['starts'] * 1000)
                elif field['starts'] in self.data['middles'][field_refr]:
                    self.data['middles'][field_refr].remove(field['starts'])
                    self.data['ends'][field_refr].append(field['starts'])
                    self.data['hold'][field_refr].append(field['starts'] * 1000)
                if field['ends'] in self.data['ends'][field_refr]:
                    self.data['ends'][field_refr].remove(field['ends'])
                    self.data['hold'][field_refr].remove(field['ends'] * 1000)
                elif field['ends'] in self.data['middles'][field_refr]:
                    self.data['middles'][field_refr].remove(field['ends'])
                    self.data['starts'][field_refr].append(field['ends'])
                    self.data['hold'][field_refr].append(field['ends'] * 1000)
                # Set field to empty; we'll have to add back into it in the validate function
                if self.types == 'tone':
                    self.fields_validated[rows] = {'starts': -1, 'middles': [],
                                                   'ends': -1, 'hold': [], 'refr': refr}
                elif self.types == 'pwm':
                    self.fields_validated[rows + pins] = {'starts': -1, 'middles': [],
                                                          'ends': -1, 'hold': [], 'refr': refr}
            except KeyError:
                pass
        elif self.types == 'output':
            pin_int = pin_to_int(refr)
            try:
                self.data['starts'][field_refr], self.data['middles'][field_refr]
                self.data['ends'][field_refr]
                self.data['hold'][field['starts'] * 1000], self.data['hold'][field['ends'] * 1000]
                # rm middles
                for i in field['middles']:
                    if i in self.data['middles'][field_refr]:
                        self.data['middles'][field_refr].remove(i)
                # rm s, e, h
                if field['starts'] in self.data['starts'][field_refr]:
                    self.data['starts'][field_refr].remove(field['starts'])
                    if self.data['hold'][field['starts'] * 1000] == pin_int:
                        self.data['hold'] = {key: self.data['hold'][key]
                                             for key in self.data['hold']
                                             if key != field['starts'] * 1000}
                    else:
                        self.data['hold'][field['starts'] * 1000] -= pin_int
                elif field['starts'] in self.data['middles'][field_refr]:
                    self.data['middles'][field_refr].remove(field['starts'])
                    self.data['ends'][field_refr].append(field['starts'])
                    if field['starts'] * 1000 in self.data['hold']:
                        self.data['hold'][field['starts'] * 1000] += pin_int
                    else:
                        self.data['hold'][field['starts'] * 1000] = pin_int
                if field['ends'] in self.data['ends'][field_refr]:
                    self.data['ends'][field_refr].remove(field['ends'])
                    if self.data['hold'][field['ends'] * 1000] == pin_int:
                        self.data['hold'] = {key: self.data['hold'][key]
                                             for key in self.data['hold']
                                             if key != field['ends'] * 1000}
                    else:
                        self.data['hold'][field['ends'] * 1000] -= pin_int
                elif field['ends'] in self.data['middles'][field_refr]:
                    self.data['middles'][field_refr].remove(field['ends'])
                    self.data['starts'][field_refr].append(field['ends'])
                    if field['ends'] * 1000 in self.data['hold']:
                        self.data['hold'][field['ends'] * 1000] += pin_int
                    else:
                        self.data['hold'][field['ends'] * 1000] = pin_int
                # set field to empty
                self.fields_validated[rows + pins] = {'starts': -1, 'middles': [],
                                                      'ends': -1, 'hold': [], 'refr': refr}
            except KeyError:
                pass

    # noinspection PyUnresolvedReferences
    def time_combine(self, on_ms, off_ms, front, back, refr):
        """Looks for adjacent time intervals and joins
        them into a single instruction"""
        if self.types in ['pwm', 'tone']:
            if front == 0 and back == 0:
                self.data['hold'][refr].append(on_ms)
                self.data['hold'][refr].append(on_ms + off_ms)
            if front == 1:
                self.data['hold'][refr].remove(on_ms)
                self.data['hold'][refr].remove(on_ms)
            if back == 1:
                self.data['hold'][refr].remove(on_ms + off_ms)
                self.data['hold'][refr].remove(on_ms + off_ms)
        elif self.types == 'output':
            pin_int = pin_to_int(refr)
            if front == 0 and back == 0:
                if on_ms not in self.data['hold']:
                    self.data['hold'][on_ms] = pin_int
                elif on_ms in self.data['hold']:
                    self.data['hold'][on_ms] += pin_int
                if on_ms + off_ms not in self.data['hold']:
                    self.data['hold'][on_ms + off_ms] = pin_int
                elif on_ms + off_ms in self.data['hold']:
                    self.data['hold'][on_ms + off_ms] += pin_int
            if front == 1:
                if self.data['hold'][on_ms] == (2 * pin_int):
                    self.data['hold'].pop(on_ms)
                else:
                    self.data['hold'][on_ms] -= (2 * pin_int)
            if back == 1:
                if self.data['hold'][on_ms + off_ms] == (2 * pin_int):
                    self.data['hold'].pop(on_ms + off_ms)
                else:
                    self.data['hold'][on_ms + off] -= (2 * pin_int)

    def pre_close(self):
        """Forces focus on button to do final validation check
        on last field entered in"""
        focus_is_entry = False
        current_focus = self.root.focus_get()
        if self.types == 'tone':
            if current_focus in self.entries:
                focus_is_entry = True
        elif self.types in ['pwm', 'output']:
            for pin in self.entries:
                if current_focus in pin:
                    focus_is_entry = True
        if focus_is_entry:
            # We indicate to entry_validate that we wish to close gui
            self.close_gui = True
            # then we force focus on the close button to
            # trigger validation on the last used entry field
            self.closebutton.focus()
        else:
            # if we aren't focused on a field, we close
            self.close()

    # noinspection PyUnresolvedReferences,PyTypeChecker
    def close(self):
        """Exits GUI Safely; otherwise we perform self.hard_exit()
        which will not save config settings"""
        # If we configured a max time higher than what it was before, update
        if self.max_time > dirs.settings.ard_last_used['packet'][3]:
            to_save = deepcopy(dirs.settings.ard_last_used)
            to_save['packet'][3] = self.max_time
            dirs.threadsafe_edit(recipient='ard_last_used', donor=to_save)
            main.ttl_time = self.max_time
            main.grab_ard_data(destroy=True)
            mins = format_secs(self.max_time / 1000, option='min')
            secs = format_secs(self.max_time / 1000, option='sec')
            main.min_entry.delete(0, Tk.END)
            main.min_entry.insert(Tk.END, '{:0>2}'.format(mins))
            main.sec_entry.delete(0, Tk.END)
            main.sec_entry.insert(Tk.END, '{:0>2}'.format(secs))
        # Retrieve data that we saved up so masterGUI can load and use
        self.return_data = []
        if self.types == 'output':
            self.return_data = self.data['hold']
        elif self.types == 'tone':
            for freq in self.data['hold']:
                self.data['hold'][freq] = sorted(self.data['hold'][freq])
                for i in range(len(self.data['hold'][freq])):
                    if i % 2 == 0:
                        self.return_data.append([self.data['hold'][freq][i],
                                                 self.data['hold'][freq][i + 1],
                                                 freq])
        elif self.types == 'pwm':
            for pin_int in self.data['hold']:
                for refr in self.data['hold'][pin_int]:
                    refr_i = str(refr)
                    freq_i, duty_i, phase_i = (int(refr_i[:-10]),
                                               int(refr_i[-10:-5]),
                                               int(refr_i[-5:]))
                    self.data['hold'][pin_int][refr] = sorted(self.data['hold'][pin_int][refr])
                    for i in range(len(self.data['hold'][pin_int][refr])):
                        if i % 2 == 0:
                            self.return_data.append([0,
                                                     self.data['hold'][pin_int][refr][i],
                                                     self.data['hold'][pin_int][refr][i + 1],
                                                     freq_i,
                                                     pin_int,
                                                     phase_i,
                                                     duty_i])
        self.root.destroy()
        self.root.quit()


class MasterGUI(GUI):
    """Main GUI.
    NOTE: Perform all GUI functions here, and here only!
    Tasks that take >1s to perform can be done in a thread,
    but interactions must be strictly through queues.
    Note on queues: do NOT process GUI objects in separate threads
    (e.g. PhotoImages, Canvas items, etc) even if they can be sent through queues.
        this WILL cause crashes under load or unexpected circumstances."""

    def __init__(self, master):
        GUI.__init__(self, master, topmost=False)
        self.master = self.root
        self.master.title('Freeze Frame Clone')
        # Fonts
        self.time_label_font = tkFont.Font(family='Arial', size=6)
        self.label_font = tkFont.Font(family='Arial', size=10)
        self.label_font_symbol = tkFont.Font(family='Arial', size=9)
        self.small_label_font = tkFont.Font(family='Arial', size=7)
        self.main_button_font = tkFont.Font(family='Arial', size=10, weight='bold')
        # Widget Configs
        self.single_widget_dim = 100
        # noinspection PyUnresolvedReferences
        self.balloon = Pmw.Balloon(master)
        ###################################################################
        # Note on Threading Control:
        # All queues initiated by child thread that puts data IN
        # All locks initiated by child thread that CONTROLS its set and clear
        ###################################################################
        # Concurrency Controls
        self.master_dump_queue = MASTER_DUMP_QUEUE
        self.master_graph_queue = MASTER_GRAPH_QUEUE
        self.thread_dump_queue = THREAD_DUMP_QUEUE
        self.process_dump_queue = PROCESS_DUMP_QUEUE
        ###########################
        # Save variables
        self.save_dir_name_used = []
        self.results_dir_used = {}
        # Arduino config variables
        self.ttl_time = dirs.settings.ard_last_used['packet'][3]
        ###########################
        # GUI setup
        self.render_photometry()
        self.render_saves()
        self.render_lj()
        self.render_arduino()
        self.render_camera()
        self.progbar_started = False
        ###########################
        # Finalize GUI window and launch
        self.process_dump_queue.put_nowait(dirs.settings)
        self.lj_proc_handler = LJProcessHandler()
        self.thread_handler = GUIThreadHandler()
        self.lj_proc_handler.start()
        self.thread_handler.start()
        self.master.after(10, self.gui_event_loop)
        self.master.after(10, self.video_stream)
        self.master.after(10, self.lj_graph_stream)
        self.clear_lj_plot = False
        self.center()

    #####################################################################
    # GUI Setup
    #####################################################################
    # noinspection PyAttributeOutsideInit
    def render_photometry(self):
        """sets up photometry component"""
        frame = Tk.LabelFrame(self.master, text='Optional Photometry Config.',
                              width=self.single_widget_dim,
                              height=self.single_widget_dim)
        frame.grid(row=0, column=0, sticky=self.ALL)
        # Variables
        self.fp_toggle_var = Tk.IntVar()
        self.fp_toggle_var.set(0)
        self.fp_statustext_var = Tk.StringVar()
        self.fp_statustext_var.set('\n[N/A]\n')
        # Buttons
        self.fp_toggle_button = Tk.Checkbutton(frame, text='Toggle Photometry On/Off',
                                               variable=self.fp_toggle_var,
                                               onvalue=1, offvalue=0,
                                               command=self.fp_toggle)
        self.fp_toggle_button.pack()
        self.fp_config_button = Tk.Button(frame,
                                          text='CONFIG',
                                          command=self.fp_config)
        self.fp_config_button.pack()
        self.fp_config_button.config(state='disabled')
        Tk.Label(frame, textvariable=self.fp_statustext_var).pack()

    # noinspection PyAttributeOutsideInit
    def render_saves(self):
        """save gui setup"""
        self.save_grab_list()
        # 1. Primary Save Frame
        frame = Tk.LabelFrame(self.master,
                              text='Data Output Save Location',
                              width=self.single_widget_dim * 2,
                              height=self.single_widget_dim)
        frame.grid(row=1, column=0, sticky=self.ALL)
        # Display chosen save name / last used save name
        self.save_status_var = Tk.StringVar()
        save_file_label = Tk.Label(frame, textvariable=self.save_status_var,
                                   relief=Tk.RAISED)
        save_file_label.pack(side=Tk.TOP, expand='yes', fill='both')
        # 2a. Secondary Save Frame: Existing Saves
        existing_frame = Tk.LabelFrame(frame, text='Select a Save Name')
        existing_frame.pack(fill='both', expand='yes')
        self.chosen_dir_var = Tk.StringVar()
        self.save_status_var.set('Last Used Save Dir.:'
                                 '\n[{}]'.format(lim_str_len(dirs.settings.save_dir.upper(), 30)))
        self.chosen_dir_var.set('{: <80}'.format(dirs.settings.save_dir))
        if len(self.save_dir_list) == 0:
            self.save_dir_menu = Tk.OptionMenu(existing_frame,
                                               self.chosen_dir_var, ' ' * 15)
        else:
            self.save_dir_menu = Tk.OptionMenu(existing_frame,
                                               self.chosen_dir_var,
                                               *self.save_dir_list,
                                               command=lambda path:
                                               self.save_button_options(inputs=path))
        self.save_dir_menu.config(width=29)
        self.save_dir_menu.grid(sticky=self.ALL, columnspan=2)
        # 2b. Secondary Save Frame: New Saves
        new_frame = Tk.LabelFrame(frame, text='Create a New Save Location')
        new_frame.pack(fill='both', expand='yes')
        self.new_save_entry = Tk.Entry(new_frame)
        self.new_save_entry.pack(side=Tk.TOP, fill='both', expand='yes')
        self.new_save_button = Tk.Button(new_frame,
                                         text='Create New',
                                         command=lambda:
                                         self.save_button_options(new=True))
        self.new_save_button.pack(side=Tk.TOP)

    # noinspection PyAttributeOutsideInit
    def render_lj(self):
        """lj config gui"""
        # Frame
        frame = Tk.LabelFrame(self.master, text='LabJack Config.',
                              width=self.single_widget_dim * 2,
                              height=self.single_widget_dim)
        frame.grid(row=2, column=0, sticky=self.ALL)
        # Variables
        self.lj_status_var = Tk.StringVar()
        channels = dirs.settings.lj_last_used['ch_num']
        freq = dirs.settings.lj_last_used['scan_freq']
        self.lj_status_var.set('Channels:\n'
                               '{}\n\n'
                               'Scan Freq: '
                               '[{}Hz]'.format(channels, freq))
        # Current State Report
        Tk.Label(frame, textvariable=self.lj_status_var).pack(side=Tk.TOP)
        # Config Button
        self.lj_config_button = Tk.Button(frame, text='CONFIG',
                                          command=self.lj_config)
        self.lj_config_button.pack(side=Tk.BOTTOM, expand=True)
        # Post experiment LabJack report frame
        report_frame = Tk.LabelFrame(self.master, text='LabJack Stream Data (20 Hz Scanning)')
        report_frame.grid(row=3, column=1, sticky=self.ALL)
        # labjack stream and post exp report items
        Tk.Label(report_frame, text='\nPost Experiment Report\n').grid(row=0, column=3, sticky=self.ALL)
        self.lj_table = SimpleTable(report_frame, 6, 5, highlight_column=2, highlight_color='#72ab97')
        self.lj_table.grid(row=1, column=3, sticky=self.ALL)
        self.lj_report_table_config()
        self.lj_graph = LiveGraph(report_frame)
        self.lj_graph.grid(row=0, column=1, columnspan=2, rowspan=1000, sticky=self.ALL)

    # noinspection PyAttributeOutsideInit
    def render_arduino(self):
        """Sets up the main progress bar, arduino config buttons,
        and various status message bars"""
        # Frame
        self.ard_preset_list = []
        self.ard_bckgrd_height = 260
        ard_frame = Tk.LabelFrame(self.master, text='Arduino Stimuli Config.',
                                  width=self.single_widget_dim * 11,
                                  height=self.ard_bckgrd_height)
        ard_frame.grid(row=0, rowspan=3, column=1, sticky=self.ALL)
        Tk.Label(ard_frame,
                 text='Last used settings shown. '
                      'Rollover individual segments for '
                      'specific stimuli configuration info.',
                 font=self.small_label_font,
                 relief=Tk.RAISED).grid(row=0, columnspan=55, sticky=self.ALL)
        # Debug Buttons
        self.debug_button = Tk.Button(ard_frame, text='DEBUG', font=self.small_label_font,
                                      command=self.gui_debug)
        self.debug_button.grid(row=0, column=80, columnspan=10, sticky=self.ALL)
        self.clr_svs_button = Tk.Button(ard_frame, text='ClrSvs', font=self.small_label_font,
                                        command=self.clear_saves)
        self.clr_svs_button.grid(row=0, column=90, columnspan=10, sticky=self.ALL)
        self.debug_chk_var = Tk.IntVar()
        if dirs.settings.debug_console:
            self.debug_chk_var.set(1)
        elif not dirs.settings.debug_console:
            self.debug_chk_var.set(0)
        Tk.Checkbutton(ard_frame, text='', variable=self.debug_chk_var,
                       command=self.debug_printing, onvalue=1,
                       offvalue=0).grid(row=0, column=79, sticky=Tk.E)
        # Main Progress Canvas
        self.ard_canvas = Tk.Canvas(ard_frame, width=1050, height=self.ard_bckgrd_height + 10)
        self.ard_canvas.grid(row=1, column=0, columnspan=100)
        self.gui_canvas_initialize()
        # Progress Bar Control Buttons
        self.prog_on = Tk.Button(ard_frame, text='START', bg='#99ccff',
                                 font=self.main_button_font)
        self.prog_on.grid(row=5, column=2, columnspan=3, stick=self.ALL)
        self.prog_off = Tk.Button(ard_frame, text='STOP', bg='#ff9999',
                                  font=self.main_button_font)
        self.prog_off.grid(row=5, column=5, stick=self.ALL)
        self.prog_on.config(command=self.progbar_run)
        self.prog_off.config(state=Tk.DISABLED,
                             command=self.progbar_stop)
        # Grab Data and Generate Progress Bar
        self.ard_grab_data()
        # Arduino Presets
        self.ard_update_preset_list()
        self.ard_preset_chosen_var = Tk.StringVar()
        self.ard_preset_chosen_var.set('{: <20}'.format('(select a preset)'))
        self.ard_preset_menu = Tk.OptionMenu(ard_frame,
                                             self.ard_preset_chosen_var,
                                             *self.ard_preset_list,
                                             command=lambda file_in:
                                             self.ard_grab_data(True, file_in))
        self.ard_preset_menu.config(width=20)
        self.ard_preset_menu.grid(row=7, column=0, columnspan=2, sticky=self.ALL)
        self.preset_save_button = Tk.Button(ard_frame, text='Save as New Preset', command=self.save_new_preset)
        self.preset_save_button.grid(row=7, column=2, columnspan=4, sticky=self.ALL)
        self.preset_save_entry = Tk.Entry(ard_frame)
        self.preset_save_entry.grid(row=6, column=2, columnspan=4, sticky=self.ALL)
        # Manual Arduino Setup
        # Total Experiment Time Config
        Tk.Label(ard_frame, text='MM',
                 font=self.time_label_font).grid(row=3, column=2, sticky=self.ALL)
        Tk.Label(ard_frame, text='SS',
                 font=self.time_label_font).grid(row=3, column=4, sticky=self.ALL)
        Tk.Label(ard_frame,
                 text='Total Experiment Time:').grid(row=3 + 1, column=0, columnspan=2, sticky=self.ALL)
        # Minutes
        self.min_entry = Tk.Entry(ard_frame, width=2)
        self.min_entry.grid(row=3 + 1, column=2, sticky=self.ALL)
        self.min_entry.insert(Tk.END, '{}'.format(format_secs(self.ttl_time / 1000, option='min')))
        Tk.Label(ard_frame, text=':').grid(row=3 + 1, column=3, sticky=self.ALL)
        # Seconds
        self.sec_entry = Tk.Entry(ard_frame, width=2)
        self.sec_entry.grid(row=3 + 1, column=4, sticky=self.ALL)
        self.sec_entry.insert(Tk.END, '{}'.format(format_secs(self.ttl_time / 1000, option='sec')))
        self.ard_time_confirm_button = Tk.Button(ard_frame, text='Confirm',
                                                 command=self.ard_get_time)
        self.ard_time_confirm_button.grid(row=3 + 1, column=5, sticky=self.ALL)
        # Stimuli Config
        self.tone_setup_button = Tk.Button(ard_frame, text='Tone Setup',
                                           command=lambda types='tone':
                                           self.ard_config(types))
        self.tone_setup_button.grid(row=5, column=0, sticky=self.ALL)
        self.out_setup_button = Tk.Button(ard_frame, text='Simple\nOutputs',
                                          command=lambda types='output':
                                          self.ard_config(types))
        self.out_setup_button.grid(row=5, rowspan=2, column=1, columnspan=1, sticky=self.ALL)
        self.pwm_setup_button = Tk.Button(ard_frame, text='PWM Setup',
                                          command=lambda types='pwm':
                                          self.ard_config(types))
        self.pwm_setup_button.grid(row=6, column=0, sticky=self.ALL)
        # Status messages for devices
        Tk.Label(ard_frame, text='Enable:', relief=Tk.RAISED,
                 font=tkFont.Font(family='Arial', size='7')).grid(row=0, column=55,
                                                                  columnspan=15,
                                                                  sticky=self.ALL)
        # arduino
        self.ard_status_bar = Tk.StringVar()
        Tk.Label(ard_frame, anchor=Tk.E, text='Arduino:  ',
                 font=self.small_label_font).grid(row=4, column=10,
                                                  columnspan=20,
                                                  sticky=Tk.E)
        ard_status_display = Tk.Label(ard_frame, anchor=Tk.W, font=self.small_label_font,
                                      textvariable=self.ard_status_bar,
                                      relief=Tk.SUNKEN)
        ard_status_display.grid(row=4, column=30, columnspan=68, sticky=self.ALL)
        self.ard_status_bar.set('null')
        self.ard_toggle_var = Tk.IntVar()
        self.ard_toggle_var.set(1)
        self.ard_toggle_button = Tk.Checkbutton(ard_frame, variable=self.ard_toggle_var, text='Arduino',
                                                onvalue=1, offvalue=0, command=lambda:
                                                self.device_status_msg_toggle(self.ard_toggle_var,
                                                                              self.ard_status_bar,
                                                                              ard_status_display,
                                                                              name='ard'))
        self.ard_toggle_button.grid(row=0, column=70, sticky=Tk.E)
        # LabJack
        self.lj_status_bar = Tk.StringVar()
        Tk.Label(ard_frame, anchor=Tk.E, text='LabJack:  ', font=self.small_label_font).grid(row=5, column=10,
                                                                                                    columnspan=20,
                                                                                                    sticky=Tk.E)
        lj_status_display = Tk.Label(ard_frame, anchor=Tk.W, font=self.small_label_font,
                                     textvariable=self.lj_status_bar,
                                     relief=Tk.SUNKEN)
        lj_status_display.grid(row=5, column=30, columnspan=68, sticky=self.ALL)
        self.lj_status_bar.set('null')
        self.lj_toggle_var = Tk.IntVar()
        self.lj_toggle_var.set(1)
        self.lj_toggle_button = Tk.Checkbutton(ard_frame, variable=self.lj_toggle_var, text='LabJack',
                                               onvalue=1, offvalue=0, command=lambda:
                                               self.device_status_msg_toggle(self.lj_toggle_var,
                                                                             self.lj_status_bar,
                                                                             lj_status_display,
                                                                             name='lj'))
        self.lj_toggle_button.grid(row=0, column=72, sticky=Tk.E)
        # Camera
        self.cmr_status_bar = Tk.StringVar()
        Tk.Label(ard_frame, anchor=Tk.E, text='Camera:  ',
                 font=self.small_label_font).grid(row=6, column=10,
                                                  columnspan=20, sticky=Tk.E)
        cmr_status_display = Tk.Label(ard_frame, anchor=Tk.W, textvariable=self.cmr_status_bar,
                                      relief=Tk.SUNKEN, font=self.small_label_font)
        cmr_status_display.grid(row=6, column=30, columnspan=68, sticky=self.ALL)
        self.cmr_status_bar.set('null')
        self.cmr_toggle_var = Tk.IntVar()
        self.cmr_toggle_var.set(1)
        self.cmr_toggle_button = Tk.Checkbutton(ard_frame, variable=self.cmr_toggle_var, text='Camera',
                                                onvalue=1, offvalue=0, command=lambda:
                                                self.device_status_msg_toggle(self.cmr_toggle_var,
                                                                              self.cmr_status_bar,
                                                                              cmr_status_display,
                                                                              name='cmr'))
        self.cmr_toggle_button.grid(row=0, column=74, sticky=Tk.E)
        # Save Status
        self.save_status_bar = Tk.StringVar()
        Tk.Label(ard_frame, anchor=Tk.E, text='Saves:  ',
                 font=self.small_label_font).grid(row=7, column=10,
                                                  columnspan=20, sticky=Tk.E)
        save_status_display = Tk.Label(ard_frame, anchor=Tk.W, textvariable=self.save_status_bar,
                                       relief=Tk.SUNKEN, font=self.small_label_font)
        save_status_display.grid(row=7, column=30, columnspan=68, sticky=self.ALL)
        self.save_status_bar.set('null')

    def gui_canvas_initialize(self):
        """Setup Progress bar Canvas"""
        # Backdrop
        self.ard_canvas.create_rectangle(0, 0,
                                         1050, self.ard_bckgrd_height,
                                         fill='black', outline='black')
        self.ard_canvas.create_rectangle(0, 35 - 1,
                                         1050, 35 + 1,
                                         fill='white')
        self.ard_canvas.create_rectangle(0, 155 - 1,
                                         1050, 155 + 1,
                                         fill='white')
        self.ard_canvas.create_rectangle(0, 15 - 1,
                                         1050, 15 + 1,
                                         fill='white')
        self.ard_canvas.create_rectangle(0, self.ard_bckgrd_height - 5 - 1,
                                         1050, self.ard_bckgrd_height - 5 + 1,
                                         fill='white')
        self.ard_canvas.create_rectangle(0, 15,
                                         0, self.ard_bckgrd_height - 5,
                                         fill='white', outline='white')
        self.ard_canvas.create_rectangle(1000, 15,
                                         1013, self.ard_bckgrd_height - 5,
                                         fill='white', outline='white')
        # Type Labels
        self.ard_canvas.create_rectangle(1000, 0,
                                         1013, 15,
                                         fill='black')
        self.ard_canvas.create_text(1000 + 7, 15 + 10,
                                    text=u'\u266b', fill='black')
        self.ard_canvas.create_rectangle(1000, 35,
                                         1013, 35,
                                         fill='black')
        self.ard_canvas.create_text(1000 + 7, 35 + 10,
                                    text='S', fill='black')
        self.ard_canvas.create_text(1000 + 7, 55 + 10,
                                    text='I', fill='black')
        self.ard_canvas.create_text(1000 + 7, 75 + 10,
                                    text='M', fill='black')
        self.ard_canvas.create_text(1000 + 7, 95 + 10,
                                    text='P', fill='black')
        self.ard_canvas.create_text(1000 + 7, 115 + 10,
                                    text='L', fill='black')
        self.ard_canvas.create_text(1000 + 7, 135 + 10,
                                    text='E', fill='black')
        self.ard_canvas.create_rectangle(1000, 155,
                                         1013, 155,
                                         fill='black')
        self.ard_canvas.create_text(1000 + 7, 175 + 10,
                                    text='P', fill='black')
        self.ard_canvas.create_text(1000 + 7, 195 + 10,
                                    text='W', fill='black')
        self.ard_canvas.create_text(1000 + 7, 215 + 10,
                                    text='M', fill='black')
        self.ard_canvas.create_rectangle(1000, self.ard_bckgrd_height - 5,
                                         1013, self.ard_bckgrd_height,
                                         fill='black')
        # Arduino Pin Labels
        self.ard_canvas.create_text(1027 + 6, 9,
                                    text='PINS', fill='white')
        self.ard_canvas.create_text(1027 + 6, 15 + 10,
                                    text='10', fill='white')
        self.ard_canvas.create_text(1027 + 6, 35 + 10,
                                    text='02', fill='white')
        self.ard_canvas.create_text(1027 + 6, 55 + 10,
                                    text='03', fill='white')
        self.ard_canvas.create_text(1027 + 6, 75 + 10,
                                    text='04', fill='white')
        self.ard_canvas.create_text(1027 + 6, 95 + 10,
                                    text='05', fill='white')
        self.ard_canvas.create_text(1027 + 6, 115 + 10,
                                    text='06', fill='white')
        self.ard_canvas.create_text(1027 + 6, 135 + 10,
                                    text='07', fill='white')
        self.ard_canvas.create_text(1027 + 6, 155 + 10,
                                    text='08', fill='white')
        self.ard_canvas.create_text(1027 + 6, 175 + 10,
                                    text='09', fill='white')
        self.ard_canvas.create_text(1027 + 6, 195 + 10,
                                    text='11', fill='white')
        self.ard_canvas.create_text(1027 + 6, 215 + 10,
                                    text='12', fill='white')
        self.ard_canvas.create_text(1027 + 6, 235 + 10,
                                    text='13', fill='white')

    def lj_report_table_config(self):
        """sets up a simple table for reporting lj stats"""
        self.lj_table.set_var(0, 1, 'Before')
        self.lj_table.set_var(0, 2, 'During')
        self.lj_table.set_var(0, 3, 'After')
        self.lj_table.set_var(0, 4, 'Total')
        self.lj_table.set_var(1, 0, 'Time (s)')
        self.lj_table.set_var(2, 0, '# Samples')
        self.lj_table.set_var(3, 0, '# Missed')
        self.lj_table.set_var(4, 0, 'Sample Hz')
        self.lj_table.set_var(5, 0, 'Scan Hz')

    # noinspection PyAttributeOutsideInit
    def render_camera(self):
        """sets up camera feed"""
        frame = Tk.LabelFrame(self.master, text='Camera Feed')
        frame.grid(row=3, column=0)
        self.camera_panel = Tk.Label(frame)
        self.camera_panel.grid(row=0, column=0, sticky=self.ALL)
        self.video_stream()

    # Genera GUI Functions (INTERACTIONS WITH THREADHANDLER AND
    # PROCESS HANDLER ARE IN THIS BLOCK)
    #####################################################################
    def gui_event_loop(self):
        """Master GUI will call this periodically to check for
        thread queue items"""
        try:
            msg = self.master_dump_queue.get_nowait()
            if dirs.settings.debug_console:
                print 'MG -- ', msg
            if msg == '<ex_succ>':
                self.master.destroy()
                self.master.quit()
            elif msg.startswith('<ex_err>'):
                msg = msg[8:].split(',')
                devices = ''
                if 'lj' in msg:
                    devices += 'LabJack, '
                if 'cmr' in msg:
                    devices += 'Camera, '
                if 'ard' in msg:
                    devices += 'Arduino, '
                devices = devices[:-2]
                tkMb.showwarning('Warning!', 'The following devices '
                                             'did not close properly: \n\n'
                                             '[{}]\n\n'
                                             'This may cause issues on subsequent'
                                             ' runs. You may wish to perform a manual'
                                             ' Hard Reset.'.format(devices))
                self.master.destroy()
                self.master.quit()
            elif msg.startswith('<lj>'):
                msg = msg[4:]
                self.lj_status_bar.set(msg)
            elif msg.startswith('<ard>'):
                msg = msg[5:]
                self.ard_status_bar.set(msg)
            elif msg.startswith('<cmr>'):
                msg = msg[5:]
                self.cmr_status_bar.set(msg)
            elif msg.startswith('<exp_end>'):
                self.run_bulk_toggle(running=False)
                self.progbar_started = False
                msg = msg[9:]
                self.save_status_bar.set(msg)
            elif msg.startswith('<threads>'):
                msg = ast.literal_eval(msg[9:])
                self.gui_debug(request_threads=False, msg=msg)
            elif msg in ['<ljst>', '<ardst>', '<cmrst>']:
                if not self.progbar_started:
                    self.progbar.start()
                    self.progbar_started = True
                elif self.progbar_started:
                    pass
            elif msg.startswith('<ljr>'):
                msg = msg[5:].split(',')
                for row in range(5):
                    for column in range(4):
                        self.lj_table.set_var(row=row + 1, column=column + 1,
                                              value=msg[row * 4 + column])
                        time.sleep(0.001)
            elif msg.startswith('<ljm>'):
                msg = msg[5:]
                self.lj_table.set_var(row=3, column=4, value=msg)
        except Queue.Empty:
            pass
        self.master.after(50, self.gui_event_loop)

    # noinspection PyDefaultArgument
    def gui_debug(self, request_threads=True, msg=[]):
        """Under the hood stuff printed when press debug button"""
        if request_threads:
            self.process_dump_queue.put_nowait('<thr>')
            return
        print '#' * 40 + '\nDEBUG\n' + '#' * 40
        print '\nSETTINGS'
        pprint(vars(dirs.settings))
        print '#' * 15
        print 'CAMERA QUEUE COUNT: {}'.format(self.thread_handler.cmr_device.data_queue.qsize())
        print '#' * 15
        print 'ACTIVE PROCESSES: {}'.format(len(multiprocessing.active_children()) + 1)
        #########################################################
        main_threads = threading.enumerate()
        main_threads_list = []
        main_threads_qfts = 0
        for i in main_threads:
            if i.name != 'QueueFeederThread':
                main_threads_list.append(i.name)
            else:
                main_threads_qfts += 1
        print ' - Main Process Threads ({}):'.format(threading.active_count())
        for i in range(len(main_threads_list)):
            print '   {} - {}'.format(i + 1, main_threads_list[i])
        print '     + [{}x] QueueFeederThreads'.format(main_threads_qfts)
        print ' - {} Threads ({}):'.format(multiprocessing.active_children()[0].name, len(msg))
        proc_threads_list = []
        proc_threads_qfts = 0
        for i in msg:
            if i[1] != 'QueueFeederThread':
                proc_threads_list.append(i[1])
            else:
                proc_threads_qfts += 1
        for i in range(len(proc_threads_list)):
            print '   {} - {}'.format(i + 1, proc_threads_list[i])
        print '     + [{}x] QueueFeederThreads'.format(proc_threads_qfts)

    def debug_printing(self):
        """more debug messages"""
        if self.debug_chk_var.get() == 1:
            dirs.settings.debug_console = True
            self.process_dump_queue.put_nowait('<dbon>')
        else:
            dirs.settings.debug_console = False
            self.process_dump_queue.put_nowait('<dboff>')

    def hard_exit(self, allow=True):
        """Handles devices before exiting for a clean close"""
        if allow:
            self.thread_dump_queue.put_nowait('<exit>')
            self.process_dump_queue.put_nowait('<exit>')
        else:
            tkMb.showwarning('Error!', 'Please STOP the experiment first.',
                             parent=self.master)

    def device_status_msg_toggle(self, var, status, display, name):
        """Hides or displays device statuses depending on
        toggle state
        var: TkInt variable that we check
        status: status msg of the device
        display: the status msg bar of the device
        """
        if var.get() == 0:
            status.set('disabled')
            display.config(state=Tk.DISABLED)
            self.thread_dump_queue.put_nowait('<{}off>'.format(name))
            if name == 'lj':
                self.process_dump_queue.put_nowait('<ljoff>')
        elif var.get() == 1:
            status.set('enabled')
            display.config(state=Tk.NORMAL)
            self.thread_dump_queue.put_nowait('<{}on>'.format(name))
            if name == 'lj':
                self.process_dump_queue.put_nowait('<ljon>')
        # experiment start button is only available if at least one device is enabled
        if self.ard_toggle_var.get() == 0 and self.lj_toggle_var.get() == 0 and self.cmr_toggle_var.get() == 0:
            self.prog_on.config(state=Tk.DISABLED)
        elif self.ard_toggle_var.get() == 1 or self.lj_toggle_var.get() == 1 or self.cmr_toggle_var.get() == 1:
            self.prog_on.config(state=Tk.NORMAL)

    def clear_saves(self):
        """Removes all settings and save directories"""
        if tkMb.askyesno('Warning!', 'This DELETES ALL settings, presets, '
                                     'and data saves!\n It should be '
                                     'used for debugging purposes only.\n\n'
                                     'Are you sure?',
                         default='no', parent=self.master):
            dirs.clear_saves()
            time.sleep(0.5)
            tkMb.showinfo('Finished', 'All settings and saves '
                                      'deleted. Program will now exit.',
                          parent=self.master)
            dirs.save_on_exit = False
            self.hard_exit()

    # Save GUI Methods
    #####################################################################
    # noinspection PyAttributeOutsideInit
    def save_grab_list(self):
        """Updates output save directories list"""
        self.save_dir_list = [d for d
                              in os.listdir(dirs.main_save_dir)
                              if os.path.isdir(dirs.main_save_dir + d)]

    # noinspection PyAttributeOutsideInit
    def save_button_options(self, inputs=None, new=False):
        """Determines whether to make a new save folder or not:"""
        self.save_grab_list()
        ready = 0
        if new:
            new_save_entry = self.new_save_entry.get().strip().lower()
            if new_save_entry in self.save_dir_list or new_save_entry in self.save_dir_name_used:
                tkMb.showinfo('Error',
                              'You cannot use an existing '
                              'Save Entry Name; '
                              'select it from the top '
                              'dialogue instead.',
                              parent=self.master)
            elif len(new_save_entry) == 0:
                tkMb.showinfo('Error!',
                              'Please enter a name '
                              'for your save directory.',
                              parent=self.master)
            else:
                ready = 1
                menu = self.save_dir_menu.children['menu']
                if len(self.save_dir_list) == 0:
                    menu.delete(0, Tk.END)
                self.save_dir_to_use = str(new_save_entry)
                self.chosen_dir_var.set(self.save_dir_to_use)
                menu.add_command(label=self.save_dir_to_use,
                                 command=lambda path=self.save_dir_to_use:
                                 self.save_button_options(inputs=path))
                self.save_dir_name_used.append(self.save_dir_to_use)
        else:
            ready = 1
            self.chosen_dir_var.set(inputs)
            self.save_dir_to_use = str(self.chosen_dir_var.get())
        if ready == 1:
            self.preresults_dir = str(dirs.main_save_dir) + self.save_dir_to_use + '/'
            if self.preresults_dir not in self.results_dir_used:
                dirs.results_dir = self.preresults_dir + '{}/'.format(format_daytime('daytime'))
                self.make_save_dir = 1
            else:
                dirs.results_dir = self.results_dir_used[self.preresults_dir]
                self.make_save_dir = 0
            self.save_status_var.set(
                'Currently Selected:\n[{}]'.format(
                    lim_str_len(self.save_dir_to_use.upper(), 30)
                )
            )
            dirs.settings.save_dir = self.save_dir_to_use

    # Camera GUI Methods
    #####################################################################
    def video_stream(self):
        """live streams video feed from camera"""
        # try:
        #     print self.thread_handler.cmr_device.data_queue.qsize()
        # except AttributeError:
        #     pass
        try:
            img = self.thread_handler.cmr_device.data_queue.get_nowait()
        except (Queue.Empty, NameError, AttributeError):
            pass
        else:
            img = PhotoImage(Image.fromarray(img).resize((288, 216), Image.ANTIALIAS))
            self.camera_panel.configure(image=img)
            self.camera_panel.image = img
        self.master.after(15, self.video_stream)

    # LabJack GUI Methods
    #####################################################################
    def lj_config(self):
        """Opens LJ GUI for settings config"""
        config = Tk.Toplevel(self.master)
        config_run = LabJackGUI(config)
        config_run.run()
        channels, freq = dirs.settings.quick_lj()
        self.lj_status_var.set('Channels:\n{}\n'
                               '\nScan Freq: [{}Hz]'.format(channels, freq))

    def lj_graph_stream(self):
        """streams data from labjack"""
        try:
            data = self.master_graph_queue.get_nowait()
            #  print self.master_graph_queue.qsize()
        except Queue.Empty:
            pass
        else:
            self.lj_graph.update_plot(data)
        if self.master_graph_queue.qsize() == 0 and self.clear_lj_plot:
            self.lj_graph.clear_plot()
            self.lj_graph.create_new_lines()
            self.clear_lj_plot = False
        self.master.after(15, self.lj_graph_stream)

    # Photometry GUI Functions
    #####################################################################
    def fp_toggle(self):
        """Toggles Photometry options On or Off"""
        if self.fp_toggle_var.get() == 1:
            self.fp_config_button.config(state=Tk.NORMAL)
            ch_num, main_freq, isos_freq = dirs.settings.quick_fp()
            state = 'LabJack Channels: {}\nMain Freq: {}Hz\nIsos Freq: {}Hz'.format(ch_num,
                                                                                    main_freq,
                                                                                    isos_freq)
            self.fp_statustext_var.set(state)
            self.fp_lj_sync()
        elif self.fp_toggle_var.get() == 0:
            shared_ch = deepcopy([i for i in dirs.settings.fp_last_used['ch_num']
                                  if i in dirs.settings.lj_last_used['ch_num']])
            if len(shared_ch) == 3:
                for i in shared_ch:
                    dirs.settings.lj_last_used['ch_num'].remove(i)
            if len(dirs.settings.lj_last_used['ch_num']) == 0:
                dirs.settings.lj_last_used['ch_num'].append(0)
            dirs.settings.lj_last_used['ch_num'].sort()
            self.lj_status_var.set('Channels:\n{}\n'
                                   '\nScan Freq: [{}Hz]'.format(dirs.settings.lj_last_used['ch_num'],
                                                                dirs.settings.lj_last_used['scan_freq']))
            self.fp_config_button.config(state=Tk.DISABLED)
            self.fp_statustext_var.set('\n[N/A]\n')

    def fp_config(self):
        """Configures photometry options"""
        fp_ch_num_old = deepcopy(dirs.settings.fp_last_used['ch_num'])
        config = Tk.Toplevel(self.master)
        config_run = PhotometryGUI(config)
        config_run.run()
        state = 'LabJack Channels: {}\nMain Freq: ' \
                '{}Hz\nIsos Freq: {}Hz'.format(config_run.ch_num,
                                               config_run.stim_freq['main'],
                                               config_run.stim_freq['isos'])
        if len([i for i in fp_ch_num_old if i in dirs.settings.lj_last_used['ch_num']]) == 3:
            for i in fp_ch_num_old:
                dirs.settings.lj_last_used['ch_num'].remove(i)
        self.fp_lj_sync()
        self.fp_statustext_var.set(state)

    def fp_lj_sync(self):
        """synchronizes fp and lj channels used"""
        ch_num = deepcopy(dirs.settings.fp_last_used['ch_num'])
        lj_ch_num = deepcopy(dirs.settings.lj_last_used['ch_num'])
        for i in ch_num:
            if i not in lj_ch_num:
                lj_ch_num.append(i)
        lj_n_ch = len(lj_ch_num)
        if lj_n_ch <= 8:
            dirs.settings.lj_last_used['ch_num'] = lj_ch_num
            dirs.settings.lj_last_used['ch_num'].sort()
            dirs.settings.lj_last_used['scan_freq'] = min(dirs.settings.lj_last_used['scan_freq'],
                                                          int(50000 / lj_n_ch))
            self.lj_status_var.set('Channels:\n{}\n'
                                   '\nScan Freq: [{}Hz]'.format(lj_ch_num, dirs.settings.lj_last_used['scan_freq']))
        elif lj_n_ch > 8:
            tkMb.showinfo('Warning!', 'Enabling photometry has increased the number of LabJack channels '
                                      'in use to {}; the maximum is 8. \n\n'
                                      'Please reconfigure LabJack settings.'.format(lj_n_ch))
            dirs.settings.lj_last_used['ch_num'] = ch_num
            self.lj_config()

    # Arduino GUI Functions
    #####################################################################
    def save_new_preset(self):
        """Saves current settings in a new preset"""
        preset_list = [d for d in dirs.settings.ard_presets]
        preset_name = self.preset_save_entry.get().strip().lower()
        if len(preset_name) == 0:
            tkMb.showerror('Error!', 'You must give your preset a name.',
                           parent=self.master)
            self.preset_save_entry.focus()
        else:
            if preset_name not in preset_list:
                to_save = deepcopy(dirs.settings.ard_last_used)
                dirs.threadsafe_edit(recipient='ard_presets', donor=to_save,
                                     name=preset_name)
                menu = self.ard_preset_menu.children['menu']
                menu.add_command(label=preset_name, command=lambda name=preset_name:
                                 self.ard_grab_data(True, name))
                self.ard_preset_chosen_var.set(preset_name)
                tkMb.showinfo('Saved!', 'Preset saved as '
                                        '[{}]'.format(preset_name),
                              parent=self.master)
            elif preset_name in preset_list:
                if tkMb.askyesno('Overwrite?', '[{}] already exists as '
                                               'a preset. Overwrite it '
                                               'anyway?'.format(preset_name),
                                 parent=self.master):
                    to_save = deepcopy(dirs.settings.ard_last_used)
                    dirs.threadsafe_edit(recipient='ard_presets', donor=to_save,
                                         name=preset_name)
                    tkMb.showinfo('Saved!', 'Preset saved as '
                                            '[{}]'.format(preset_name),
                                  parent=self.master)

    def ard_config(self, types):
        """Presents the requested Arduino GUI"""
        config = Tk.Toplevel(self.master)
        config_run = ArduinoGUI(config)
        if types == 'tone':
            config_run.tone_setup()
        elif types == 'output':
            config_run.output_setup()
        elif types == 'pwm':
            config_run.pwm_setup()
        config_run.run()
        # Now we load these settings
        # back into settings.ard_last_used
        if not config_run.hard_closed:
            data = config_run.return_data
            if config_run.types == 'tone':
                dirs.settings.ard_last_used['packet'][4] = len(data)
                dirs.settings.ard_last_used['tone_pack'] = []
                for i in data:
                    dirs.settings.ard_last_used['tone_pack'].append(["<LLH"] + i)
                dirs.settings.ard_last_used['tone_pack'] = sorted(dirs.settings.ard_last_used['tone_pack'],
                                                                  key=itemgetter(1))
            if config_run.types == 'output':
                dirs.settings.ard_last_used['packet'][5] = len(data)
                dirs.settings.ard_last_used['out_pack'] = []
                for i in data:
                    dirs.settings.ard_last_used['out_pack'].append(["<LB", i, data[i]])
                dirs.settings.ard_last_used['out_pack'] = sorted(dirs.settings.ard_last_used['out_pack'],
                                                                 key=itemgetter(1))
            if config_run.types == 'pwm':
                dirs.settings.ard_last_used['packet'][6] = len(data)
                dirs.settings.ard_last_used['pwm_pack'] = []
                for i in data:
                    dirs.settings.ard_last_used['pwm_pack'].append(["<LLLfBBf"] + i)
                dirs.settings.ard_last_used['pwm_pack'] = sorted(dirs.settings.ard_last_used['pwm_pack'],
                                                                 key=itemgetter(2))
            self.ard_grab_data(destroy=True)

    def ard_get_time(self):
        """Gets total exp time from GUI input and uses it if if is >= max time
        of all stimuli components"""
        max_stim_time = []
        for i in dirs.settings.ard_last_used['tone_pack']:
            max_stim_time.append(i[2])
        for i in dirs.settings.ard_last_used['out_pack']:
            max_stim_time.append(i[1])
        for i in dirs.settings.ard_last_used['pwm_pack']:
            max_stim_time.append(i[3])
        try:
            max_stim_time = max(max_stim_time)
        except ValueError:
            max_stim_time = 0
        try:
            # Grab Inputs
            mins = int(self.min_entry.get().strip())
            secs = int(self.sec_entry.get().strip())
            mins += secs // 60
            secs %= 60
            # Update Fields if improper format entered
            self.min_entry.delete(0, Tk.END)
            self.min_entry.insert(Tk.END, '{:0>2}'.format(mins))
            self.sec_entry.delete(0, Tk.END)
            self.sec_entry.insert(Tk.END, '{:0>2}'.format(secs))
            # Update Vairbales
            self.ttl_time = (mins * 60 + secs) * 1000
            if self.ttl_time < max_stim_time:
                self.ttl_time = deepcopy(max_stim_time)
                max_stim_time /= 1000
                mins = max_stim_time // 60
                secs = max_stim_time % 60
                tkMb.showinfo('Error!', 'Total time cannot be less than '
                                        '[{}:{}] because one of the stimuli segments'
                                        ' exceeds this value. \n\n'
                                        'Reconfigure your stimuli if you wish to'
                                        ' reduce total '
                                        'time further.'.format(mins, secs))
                self.min_entry.delete(0, Tk.END)
                self.min_entry.insert(Tk.END, '{:0>2}'.format(mins))
                self.sec_entry.delete(0, Tk.END)
                self.sec_entry.insert(Tk.END, '{:0>2}'.format(secs))
            dirs.settings.ard_last_used['packet'][3] = self.ttl_time
            self.ard_grab_data(destroy=True)
        except ValueError:
            tkMb.showinfo('Error!',
                          'Time must be entered as integers',
                          parent=self.master)

    # noinspection PyAttributeOutsideInit
    def ard_update_preset_list(self):
        """List of all Arduino Presets"""
        self.ard_preset_list = [i for i in dirs.settings.ard_presets]

    # noinspection PyAttributeOutsideInit
    def ard_grab_data(self, destroy=False, load=False):
        """Obtain arduino data from saves"""
        # If load is false, then we load from settings.frcl
        if load is not False:
            # Then load must be a preset name.
            dirs.settings.ard_last_used = deepcopy(dirs.settings.ard_presets[load])
            # Update Total Time Fields
            last_used_time = dirs.settings.ard_last_used['packet'][3] / 1000
            self.min_entry.delete(0, Tk.END)
            self.sec_entry.delete(0, Tk.END)
            self.min_entry.insert(Tk.END, '{}'.format(format_secs(last_used_time,
                                                                  option='min')))
            self.sec_entry.insert(Tk.END, '{}'.format(format_secs(last_used_time,
                                                                  option='sec')))
            self.ard_preset_chosen_var.set(load)
        if destroy:
            self.ard_canvas.delete(self.progress_shape)
            self.ard_canvas.delete(self.progress_text)
            for i in self.v_bars:
                self.ard_canvas.delete(i)
            for i in self.bar_times:
                self.ard_canvas.delete(i)
            for i in self.tone_bars:
                self.balloon.tagunbind(self.ard_canvas, i)
                self.ard_canvas.delete(i)
            for i in self.out_bars:
                self.balloon.tagunbind(self.ard_canvas, i)
                self.ard_canvas.delete(i)
            for i in self.pwm_bars:
                self.balloon.tagunbind(self.ard_canvas, i)
                self.ard_canvas.delete(i)
        divisor = 5 + 5 * int(dirs.settings.ard_last_used['packet'][3] / 300000)
        segment = float(dirs.settings.ard_last_used['packet'][3] / 1000) / divisor
        self.v_bars = [[]] * (1 + int(round(segment)))
        self.bar_times = [[]] * (1 + int(round(segment)))
        for i in range(int(round(segment))):
            if i > 0:
                if i % 2 != 0:
                    self.v_bars[i] = self.ard_canvas.create_rectangle(i * (1000.0 / segment) - 1,
                                                                      15,
                                                                      i * (1000.0 / segment) + 1,
                                                                      self.ard_bckgrd_height - 5,
                                                                      fill='white')
                if i % 2 == 0:
                    self.v_bars[i] = self.ard_canvas.create_rectangle(i * (1000.0 / segment) - 1,
                                                                      15,
                                                                      i * (1000.0 / segment) + 1,
                                                                      self.ard_bckgrd_height,
                                                                      fill='white')
                    self.bar_times[i] = self.ard_canvas.create_text(i * (1000.0 / segment),
                                                                    self.ard_bckgrd_height + 8,
                                                                    text=format_secs(divisor * i),
                                                                    fill='black',
                                                                    font=self.time_label_font)
                if i == int(round(segment)) - 1 and (i + 1) % 2 == 0 and (i + 1) * (1000.0 / segment) <= 1001:
                    if round((i + 1) * (1000.0 / segment)) != 1000.0:
                        self.v_bars[i + 1] = self.ard_canvas.create_rectangle((i + 1) * (1000.0 / segment) - 1,
                                                                              15,
                                                                              (i + 1) * (1000.0 / segment) + 1,
                                                                              self.ard_bckgrd_height,
                                                                              fill='white')
                    elif round((i + 1) * (1000.0 / segment)) == 1000:
                        self.v_bars[i + 1] = self.ard_canvas.create_rectangle((i + 1) * (1000.0 / segment) - 1,
                                                                              self.ard_bckgrd_height - 5,
                                                                              (i + 1) * (1000.0 / segment) + 1,
                                                                              self.ard_bckgrd_height,
                                                                              fill='white')
                    self.bar_times[i + 1] = self.ard_canvas.create_text((i + 1) * (1000.0 / segment),
                                                                        self.ard_bckgrd_height + 8,
                                                                        text=format_secs(divisor * (i + 1)),
                                                                        fill='black',
                                                                        font=self.time_label_font)
                if i == int(round(segment)) - 1 and (i + 1) % 2 != 0 and (i + 1) * (1000.0 / segment) <= 1001:
                    if round((i + 1) * (1000.0 / segment)) != 1000.0:
                        self.v_bars[i + 1] = self.ard_canvas.create_rectangle((i + 1) * (1000.0 / segment) - 1,
                                                                              15,
                                                                              (i + 1) * (1000.0 / segment) + 1,
                                                                              self.ard_bckgrd_height,
                                                                              fill='white')
                    elif round((i + 1) * (1000.0 / segment)) == 1000:
                        self.v_bars[i + 1] = self.ard_canvas.create_rectangle((i + 1) * (1000.0 / segment) - 1,
                                                                              self.ard_bckgrd_height - 5,
                                                                              (i + 1) * (1000.0 / segment) + 1,
                                                                              self.ard_bckgrd_height,
                                                                              fill='white')
        self.tone_data, self.out_data, self.pwm_data = -1, -1, -1
        self.tone_bars = []
        if len(dirs.settings.ard_last_used['tone_pack']) != 0:
            self.tone_data = self.ard_decode_data('tone', dirs.settings.ard_last_used['tone_pack'])
            self.tone_bars = [[]] * len(self.tone_data)
            for i in range(len(self.tone_data)):
                self.tone_bars[i] = self.ard_canvas.create_rectangle(self.tone_data[i][0],
                                                                     0 + 15,
                                                                     self.tone_data[i][1] + self.tone_data[i][0],
                                                                     35, fill='yellow', outline='blue')
                self.balloon.tagbind(self.ard_canvas,
                                     self.tone_bars[i],
                                     '{} - {}\n{} Hz'.format(
                                         format_secs(
                                             self.tone_data[i][4] / 1000),
                                         format_secs(
                                             self.tone_data[i][5] / 1000),
                                         self.tone_data[i][3]))
        self.out_bars = []
        if len(dirs.settings.ard_last_used['out_pack']) != 0:
            pin_ids = range(2, 8)
            self.out_data = self.ard_decode_data('output',
                                                 dirs.settings.ard_last_used['out_pack'])
            self.out_bars = [[]] * len(self.out_data)
            for i in range(len(self.out_data)):
                y_pos = 35 + (pin_ids.index(self.out_data[i][3])) * 20
                self.out_bars[i] = self.ard_canvas.create_rectangle(self.out_data[i][0],
                                                                    y_pos,
                                                                    self.out_data[i][1] + self.out_data[i][0],
                                                                    y_pos + 20,
                                                                    fill='yellow', outline='blue')
                self.balloon.tagbind(self.ard_canvas,
                                     self.out_bars[i],
                                     '{} - {}\nPin {}'.format(
                                         format_secs(
                                             self.out_data[i][4] / 1000),
                                         format_secs(
                                             self.out_data[i][5] / 1000),
                                         self.out_data[i][3]))
        self.pwm_bars = []
        if len(dirs.settings.ard_last_used['pwm_pack']) != 0:
            pin_ids = range(8, 14)
            pin_ids.remove(10)
            self.pwm_data = self.ard_decode_data('pwm', dirs.settings.ard_last_used['pwm_pack'])
            self.pwm_bars = [[]] * len(self.pwm_data)
            for i in range(len(self.pwm_data)):
                y_pos = 155 + (pin_ids.index(self.pwm_data[i][3])) * 20
                self.pwm_bars[i] = self.ard_canvas.create_rectangle(self.pwm_data[i][0],
                                                                    y_pos,
                                                                    self.pwm_data[i][1] + self.pwm_data[i][0],
                                                                    y_pos + 20,
                                                                    fill='yellow', outline='blue')
                self.balloon.tagbind(self.ard_canvas,
                                     self.pwm_bars[i],
                                     ('{} - {}\n'
                                      'Pin {}\n'
                                      'Freq: {}Hz\n'
                                      'Duty Cycle: {}%\n'
                                      'Phase Shift: {}' + u'\u00b0').format(
                                         format_secs(self.pwm_data[i][7] / 1000),
                                         format_secs(self.pwm_data[i][8] / 1000),
                                         self.pwm_data[i][3],
                                         self.pwm_data[i][4],
                                         self.pwm_data[i][5],
                                         self.pwm_data[i][6]))
        self.progress_shape = self.ard_canvas.create_rectangle(-1, 0,
                                                               1, self.ard_bckgrd_height,
                                                               fill='red')
        self.progress_text = self.ard_canvas.create_text(35, 0,
                                                         fill='white',
                                                         anchor=Tk.N,
                                                         font=self.small_label_font)
        self.progbar = ProgressBar(self.master,
                                   self.ard_canvas,
                                   self.progress_shape,
                                   self.progress_text,
                                   dirs.settings.ard_last_used['packet'][3])

    @staticmethod
    def ard_decode_data(name, data_source):
        """Read packed up Arduino Data and puts it in proper format"""
        time_seg = float(dirs.settings.ard_last_used['packet'][3]) / 1000
        if name == 'tone':
            start, on = 1, 2
        elif name == 'pwm':
            start, on = 2, 3
        elif name == 'output':
            indiv_trigs, indiv_times, trig_times, final_intv = [], [], {}, []
            start, on, = 1, 2
            for i in data_source:
                triggers = check_binary(i[2], 'D')
                for n in triggers:
                    indiv_trigs.append(n)
                    indiv_times.append(i[1])
            for i in range(len(indiv_trigs)):
                n = indiv_trigs[i]
                try:
                    trig_times[n].append(indiv_times[i])
                except KeyError:
                    trig_times[n] = [indiv_times[i]]
            for i in trig_times:
                for n in range(len(trig_times[i])):
                    if n % 2 == 0:
                        final_intv.append([i,
                                           trig_times[i][n],
                                           trig_times[i][n + 1]])
            final_intv = sorted(final_intv,
                                key=itemgetter(1))
            data_source = final_intv
        ard_data = []
        for i in data_source:
            start_space = (float(i[start]) / time_seg)
            on_space = float(i[on]) / time_seg - start_space
            if on_space == 0:
                start_space -= 1
                on_space = 1
            off_space = 1000 - on_space - start_space
            if name == 'tone':
                ard_data.append([start_space,
                                 on_space,
                                 off_space,
                                 i[3],
                                 i[start],
                                 i[on]])
            elif name == 'pwm':
                ard_data.append([start_space,
                                 on_space,
                                 off_space,
                                 check_binary(i[5], 'B')[0],
                                 i[4],
                                 i[7],
                                 i[6],
                                 i[start],
                                 i[on]])
            elif name == 'output':
                ard_data.append([start_space,
                                 on_space,
                                 off_space,
                                 i[0],
                                 i[start],
                                 i[on]])
        return ard_data

    # THESE FUNCTIONS INTERACT WITH THREAD HANDLER THROUGH QUEUES
    #####################################################################
    # Running the Experiment
    #####################################################################
    # noinspection PyAttributeOutsideInit
    def progbar_run(self):
        """Check if valid settings, make directories, and start progress bar"""
        # Check folders are available
        self.clear_lj_plot = True
        self.lj_table.clear()
        if len(self.save_dir_list) == 0 and len(self.results_dir_used) == 0 and dirs.settings.save_dir == '':
            tkMb.showinfo('Error!',
                          'You must first create a directory to save data output.',
                          parent=self.master)
            return
        # Make sure we actually have a place to save files:
        if len(self.results_dir_used) == 0:
            self.preresults_dir = str(dirs.main_save_dir) + dirs.settings.save_dir + '/'
            dirs.results_dir = self.preresults_dir + '{}/'.format(format_daytime('daytime'))
            self.make_save_dir = 1
            self.save_status_var.set('Currently Selected:\n[{}]'.format(
                lim_str_len(dirs.settings.save_dir.upper(), 30)))
        if self.make_save_dir == 1 or not os.path.isdir(dirs.results_dir):
            os.makedirs(dirs.results_dir)
            self.results_dir_used[self.preresults_dir] = dirs.results_dir
            self.make_save_dir = 0
            self.save_grab_list()
        # Run
        run_msg = '<run>'
        self.thread_dump_queue.put_nowait(run_msg)
        self.process_dump_queue.put_nowait(run_msg)
        self.process_dump_queue.put_nowait(dirs.settings)
        self.process_dump_queue.put_nowait(dirs.results_dir)
        self.save_status_bar.set('Started.')
        self.run_bulk_toggle(running=True)

    def progbar_stop(self):
        """performs a hard stop on the experiment"""
        self.thread_dump_queue.put_nowait('<hardstop>')
        self.process_dump_queue.put_nowait('<hardstop>')
        self.progbar.stop()

    def run_bulk_toggle(self, running):
        """Toggles all non-essential buttons to active
        or disabled based on running state"""
        if running:
            self.master.protocol('WM_DELETE_WINDOW',
                                 lambda: self.hard_exit(allow=False))
            self.prog_off.config(state=Tk.NORMAL)
            self.prog_on.config(state=Tk.DISABLED)
            self.fp_toggle_button.config(state=Tk.DISABLED)
            self.fp_config_button.config(state=Tk.DISABLED)
            self.save_dir_menu.config(state=Tk.DISABLED)
            self.new_save_entry.config(state=Tk.DISABLED)
            self.new_save_button.config(state=Tk.DISABLED)
            self.lj_config_button.config(state=Tk.DISABLED)
            # self.debug_button.config(state=Tk.DISABLED)
            self.clr_svs_button.config(state=Tk.DISABLED)
            self.ard_preset_menu.config(state=Tk.DISABLED)
            self.min_entry.config(state=Tk.DISABLED)
            self.sec_entry.config(state=Tk.DISABLED)
            self.ard_time_confirm_button.config(state=Tk.DISABLED)
            self.tone_setup_button.config(state=Tk.DISABLED)
            self.out_setup_button.config(state=Tk.DISABLED)
            self.pwm_setup_button.config(state=Tk.DISABLED)
            self.ard_toggle_button.config(state=Tk.DISABLED)
            self.lj_toggle_button.config(state=Tk.DISABLED)
            self.cmr_toggle_button.config(state=Tk.DISABLED)
            self.preset_save_button.config(state=Tk.DISABLED)
            self.preset_save_entry.config(state=Tk.DISABLED)
        if not running:
            self.master.protocol('WM_DELETE_WINDOW', self.hard_exit)
            self.prog_off.config(state=Tk.DISABLED)
            self.prog_on.config(state=Tk.NORMAL)
            self.fp_toggle_button.config(state=Tk.NORMAL)
            if self.fp_toggle_var.get() == 1:
                self.fp_config_button.config(state=Tk.NORMAL)
            self.save_dir_menu.config(state=Tk.NORMAL)
            self.new_save_entry.config(state=Tk.NORMAL)
            self.new_save_button.config(state=Tk.NORMAL)
            self.lj_config_button.config(state=Tk.NORMAL)
            # self.debug_button.config(state=Tk.NORMAL)
            self.clr_svs_button.config(state=Tk.NORMAL)
            self.ard_preset_menu.config(state=Tk.NORMAL)
            self.min_entry.config(state=Tk.NORMAL)
            self.sec_entry.config(state=Tk.NORMAL)
            self.ard_time_confirm_button.config(state=Tk.NORMAL)
            self.tone_setup_button.config(state=Tk.NORMAL)
            self.out_setup_button.config(state=Tk.NORMAL)
            self.pwm_setup_button.config(state=Tk.NORMAL)
            self.ard_toggle_button.config(state=Tk.NORMAL)
            self.lj_toggle_button.config(state=Tk.NORMAL)
            self.cmr_toggle_button.config(state=Tk.NORMAL)
            self.preset_save_button.config(state=Tk.NORMAL)
            self.preset_save_entry.config(state=Tk.NORMAL)


#################################################################
# Concurrency Processors
class GUIThreadHandler(threading.Thread):
    """Handles all non-gui processing and communicates
    with GUI via queue polling"""

    def __init__(self):
        threading.Thread.__init__(self)
        self.daemon = True
        self.name = 'Subthread Handler'
        # Thread handling
        # Queues
        self.master_dump_queue = MASTER_DUMP_QUEUE
        self.thread_dump_queue = THREAD_DUMP_QUEUE
        self.process_dump_queue = PROCESS_DUMP_QUEUE
        #####
        self.lj_read_ready_lock = LJ_READ_READY_LOCK
        self.lj_exp_ready_lock = LJ_EXP_READY_LOCK
        self.ard_ready_lock = ARD_READY_LOCK
        self.cmr_ready_lock = CMR_READY_LOCK
        # Devices
        self.lj_connected = False
        self.lj_running = False
        self.cmr_device = None
        self.ard_device = None
        # Use this device?
        self.lj_use = True
        self.ard_use = True
        self.cmr_use = True
        self.lj_created = False
        self.ard_created = False
        self.cmr_created = False
        self.devices_created = False
        # main handler loop
        self.hard_stop_experiment = False
        self.exp_is_running = False
        self.running = True

    def run(self):
        """Periodically processes queue instructions from
        master gui; (starts the thread)"""
        # because the camera needs to immediately start streaming,
        # we set it up now if possible
        self.cmr_device = FireFly(lj_exp_ready_lock=self.lj_exp_ready_lock,
                                  cmr_ready_lock=self.cmr_ready_lock,
                                  ard_ready_lock=self.ard_ready_lock,
                                  master_gui_queue=self.master_dump_queue)
        if self.cmr_device.initialize():
            camera_thread = threading.Thread(target=self.cmr_device.camera_run,
                                             name='Camera Stream')
            camera_thread.daemon = True
            camera_thread.start()
            self.cmr_created = True
        # loops until we exit the program
        while self.running:
            time.sleep(0.01)
            try:
                msg = self.thread_dump_queue.get_nowait()
            except Queue.Empty:
                pass
            else:
                if msg == '<run>':
                    if not self.devices_created:
                        if all(self.create_devices()):
                            self.devices_created = True
                        else:
                            self.master_dump_queue.put_nowait('<exp_end>*** Failed to Initiate '
                                                              'one of the selected devices.')
                    if self.devices_created and all(self.check_connections()):
                        # devices needed are connected. start exp
                        if self.cmr_use:
                            self.cmr_device.recording = True
                        if self.lj_use:
                            self.lj_running = True
                        if self.ard_use:
                            ard_thread = threading.Thread(target=self.ard_device.run_experiment,
                                                          name='Arduino Control')
                            ard_thread.daemon = True
                            ard_thread.start()
                            self.ard_device.running = True
                        self.exp_is_running = True
                    else:
                        self.master_dump_queue.put_nowait('<exp_end>*** Failed to Initiate '
                                                          'one of the selected devices.')
                elif msg == '<hardstop>':
                    self.hard_stop_experiment = True
                    try:
                        self.ard_device.hard_stopped = True
                        self.ard_device.running = False
                    except AttributeError:
                        pass
                    try:
                        self.cmr_device.hard_stopped = True
                        self.cmr_device.recording = False
                    except AttributeError:
                        pass
                elif msg == '<ljoff>':
                    self.lj_use = False
                elif msg == '<ardoff>':
                    self.ard_use = False
                    self.ard_ready_lock.set()
                elif msg == '<cmroff>':
                    self.cmr_use = False
                    self.cmr_ready_lock.set()
                elif msg == '<ljon>':
                    self.lj_use = True
                    self.devices_created = False
                elif msg == '<ardon>':
                    self.ard_use = True
                    self.ard_ready_lock.clear()
                    self.devices_created = False
                elif msg == '<cmron>':
                    self.cmr_use = True
                    self.cmr_ready_lock.clear()
                    self.devices_created = False
                elif msg == '<lj_run_false>':
                    self.lj_running = False
                elif msg == '<exit>':
                    self.close_devices()
                if dirs.settings.debug_console:
                    print 'TH -- ', msg
            if self.devices_created and self.exp_is_running:
                devices_to_check = []
                if self.cmr_use:
                    devices_to_check.append(self.cmr_device.recording)
                if self.lj_use:
                    devices_to_check.append(self.lj_running)
                if self.ard_use:
                    devices_to_check.append(self.ard_device.running)
                if not any(devices_to_check):
                    msg_with_save_status = '<exp_end>'
                    if self.hard_stop_experiment:
                        msg_with_save_status += 'Terminated.'
                        self.hard_stop_experiment = False
                    elif not self.hard_stop_experiment:
                        msg_with_save_status += "Data saved in '{}'".format(dirs.results_dir)
                    self.master_dump_queue.put_nowait(msg_with_save_status)
                    self.exp_is_running = False

    def check_connections(self):
        """Checks that user enabled devices are ready to go"""
        devices_ready = []
        if self.lj_use:
            lj_conn_status = self.thread_dump_queue.get()
            if lj_conn_status == '<lj_connected>':
                self.lj_connected = True
            elif lj_conn_status == '<lj_conn_failed>':
                self.lj_connected = False
            devices_ready.append(self.lj_connected)
        if self.ard_use:
            self.ard_device.check_connection()
            devices_ready.append(self.ard_device.connected)
        if self.cmr_use:
            # we already checked connection in the cmr
            # initialize function.
            devices_ready.append(self.cmr_device.connected)
        return devices_ready

    def create_devices(self):
        """Creates device instances"""
        devices_ready = []
        # Labjack
        if self.lj_use and not self.lj_created:
            lj_status = self.thread_dump_queue.get()
            if dirs.settings.debug_console:
                print 'TH -- ', lj_status
            if lj_status == '<lj_created>':
                self.lj_created = True
            elif lj_status == '<lj_create_failed>':
                self.lj_created = False
            devices_ready.append(self.lj_created)
        # camera
        if self.cmr_use and not self.cmr_created:
            if self.cmr_device.initialize():
                camera_thread = threading.Thread(target=self.cmr_device.camera_run,
                                                 name='CameraStreamThread')
                camera_thread.daemon = True
                camera_thread.start()
                self.cmr_created = True
                devices_ready.append(self.cmr_created)
        # arduino
        if self.ard_use and not self.ard_created:
            self.ard_device = ArduinoUno(lj_exp_ready_lock=self.lj_exp_ready_lock,
                                         ard_ready_lock=self.ard_ready_lock,
                                         cmr_ready_lock=self.cmr_ready_lock,
                                         master_gui_queue=self.master_dump_queue)
            self.master_dump_queue.put_nowait('<ard>Arduino initialized! Waiting for'
                                              ' other selected devices to begin...')
            self.ard_created = True
            devices_ready.append(self.ard_created)
        return devices_ready

    def close_devices(self):
        """attempts to close hardware properly, and reports
        close status to GUI"""
        cmr_error, ard_error = False, False
        lj_error = self.thread_dump_queue.get()
        if lj_error == '<lj_ex_err>':
            lj_error = True
        elif lj_error == '<lj_ex_succ>':
            lj_error = False
        # camera
        try:
            self.cmr_device.close()
            if dirs.settings.debug_console:
                print 'Camera Closed Successfully.'
        except fc2.ApiError:
            cmr_error = True
        except AttributeError:
            pass
        # ... and arduino
        try:
            self.ard_device.serial.close()
            if dirs.settings.debug_console:
                print 'Arduino Closed Successfully.'
        except serial.SerialException:
            ard_error = True
        except AttributeError:
            pass
        if any((lj_error, cmr_error, ard_error)):
            error_msg = '<ex_err>'
            if lj_error:
                error_msg += 'lj,'
            if cmr_error:
                error_msg += 'cmr,'
            if ard_error:
                error_msg += 'ard,'
            error_msg = error_msg[:-1]
            self.master_dump_queue.put_nowait(error_msg)
        else:
            self.master_dump_queue.put_nowait('<ex_succ>')
        self.running = False


class LJProcessHandler(multiprocessing.Process):
    """Handles all labjack instructions on a separate process
    for maximum labjack stream rates"""

    def __init__(self):
        multiprocessing.Process.__init__(self)
        self.daemon = True
        self.name = 'LabJack Process Handler'
        # Concurrency Controls
        self.master_dump_queue = MASTER_DUMP_QUEUE
        self.master_graph_queue = MASTER_GRAPH_QUEUE
        self.thread_dump_queue = THREAD_DUMP_QUEUE
        self.process_dump_queue = PROCESS_DUMP_QUEUE
        #####
        self.lj_read_ready_lock = LJ_READ_READY_LOCK
        self.lj_exp_ready_lock = LJ_EXP_READY_LOCK
        self.ard_ready_lock = ARD_READY_LOCK
        self.cmr_ready_lock = CMR_READY_LOCK
        # LJ parameters
        self.lj_device = None
        # Use this device?
        self.lj_use = True
        self.lj_created = False
        # main handler loop
        self.hard_stop_experiment = False
        self.exp_is_running = False
        self.running = True
        # Grab settings from main process
        self.settings = None
        self.results_dir = None

    def run(self):
        """periodically checks for instructions from
        self.process_dump_queue and performs them"""
        self.settings = self.process_dump_queue.get()
        while self.running:
            time.sleep(0.01)
            try:
                msg = self.process_dump_queue.get_nowait()
            except Queue.Empty:
                pass
            else:
                if msg == '<run>':
                    # grab dirs.settings from main process
                    self.settings = self.process_dump_queue.get()
                    self.results_dir = self.process_dump_queue.get()
                    self.create_lj()
                    if self.lj_created and self.check_lj_connected():
                        if self.lj_use:
                            lj_stream_thread = threading.Thread(target=self.lj_device.read_stream_data,
                                                                args=(self.settings,),
                                                                name='LabJack Stream')
                            lj_stream_thread.daemon = True
                            lj_write_thread = threading.Thread(target=self.lj_device.data_write_plot,
                                                               args=(self.results_dir,),
                                                               name='LabJack Data Write')
                            lj_write_thread.daemon = True
                            lj_write_thread.start()
                            lj_stream_thread.start()
                            self.lj_device.running = True
                            self.exp_is_running = True
                elif msg == '<hardstop>':
                    self.hard_stop_experiment = True
                    try:
                        self.lj_device.hard_stopped = True
                        self.lj_device.running = False
                    except AttributeError:
                        pass
                elif msg == '<ljoff>':
                    self.lj_use = False
                    self.lj_read_ready_lock.set()
                    self.lj_exp_ready_lock.set()
                elif msg == '<ljon>':
                    self.lj_use = True
                    self.lj_read_ready_lock.clear()
                    self.lj_exp_ready_lock.clear()
                elif msg == '<dbon>':
                    self.settings.debug_console = True
                elif msg == '<dboff>':
                    self.settings.debug_console = False
                elif msg == '<exit>':
                    self.close_lj()
                elif msg == '<thr>':
                    threads = threading.enumerate()
                    thread_list = []
                    for i in range(len(threads)):
                        thread_list.append([i, threads[i].name])
                    self.master_dump_queue.put_nowait('<threads>{}'.format(thread_list))
                if self.settings.debug_console:
                    print 'CP -- ', msg
            if self.lj_created and not self.lj_device.running and self.exp_is_running:
                self.thread_dump_queue.put_nowait('<lj_run_false>')
                self.exp_is_running = False
                self.hard_stop_experiment = False

    def create_lj(self):
        """creates new LJ object"""
        if self.lj_use and not self.lj_created:
            try:
                self.master_dump_queue.put_nowait('<lj>Creating LabJack Instance...')
                self.lj_device = LabJackU6(ard_ready_lock=self.ard_ready_lock,
                                           cmr_ready_lock=self.cmr_ready_lock,
                                           lj_read_ready_lock=self.lj_read_ready_lock,
                                           lj_exp_ready_lock=self.lj_exp_ready_lock,
                                           master_dump_queue=self.master_dump_queue,
                                           master_graph_queue=self.master_graph_queue)
                self.lj_created = True
                self.thread_dump_queue.put_nowait('<lj_created>')
            except (LabJackException, LowlevelErrorException):
                self.master_dump_queue.put_nowait('<lj>** LabJack could not be initialized! '
                                                  'Please perform a manual hard reset (disconnect'
                                                  '/reconnect)')
                self.lj_created = False
                self.thread_dump_queue.put_nowait('<lj_create_failed>')

    def check_lj_connected(self):
        """checks that the labjack is connected if requested"""
        if self.lj_use:
            self.lj_device.check_connection()
            if self.lj_device.connected:
                self.thread_dump_queue.put_nowait('<lj_connected>')
            elif not self.lj_device.connected:
                self.thread_dump_queue.put_nowait('<lj_conn_failed>')
            return self.lj_device.connected

    def close_lj(self):
        """closes the labjack"""
        lj_error = False
        try:
            self.lj_device.streamStop()
            self.lj_device.close()
            if self.settings.debug_console:
                print 'LabJack Closed Successfully [SC]'
        except (LabJackException, LowlevelErrorException):
            try:
                self.lj_device.close()
                self.lj_device.streamStop()
                if self.settings.debug_console:
                    print 'LabJack Closed Successfully [CS]'
            except (LabJackException, LowlevelErrorException):
                try:
                    self.lj_device.close()
                    if self.settings.debug_console:
                        print 'LabJack Closed Successfully [N]'
                except LabJackException:
                    if self.settings.debug_console:
                        print 'LabJack Close Unsuccessful.'
                    lj_error = True
        except AttributeError:
            pass
        if lj_error:
            self.thread_dump_queue.put_nowait('<lj_ex_err>')
        elif not lj_error:
            self.thread_dump_queue.put_nowait('<lj_ex_succ>')
        self.running = False


####################################################################
# Device Hardware Control and Reporting
class LabJackU6(u6.U6):
    """LabJack control functions"""

    def __init__(self, ard_ready_lock, cmr_ready_lock,
                 lj_read_ready_lock, lj_exp_ready_lock,
                 master_dump_queue, master_graph_queue):
        u6.U6.__init__(self)
        self.running = False
        self.hard_stopped = False
        self.connected = False
        self.time_start_read = datetime.now()
        ##########################################################
        # note on concurrency controls:
        # since the LJ is created AFTER creating the separate process,
        # it won't have access to main process globals;
        # the locks and queues must be passed from the process handler,
        # which would have had access at time of process creation
        ##########################################################
        # Concurrency Controls
        # Locks to wait on:
        self.ard_ready_lock = ard_ready_lock
        self.cmr_ready_lock = cmr_ready_lock
        # Locks to control:
        self.lj_read_ready_lock = lj_read_ready_lock
        self.lj_exp_ready_lock = lj_exp_ready_lock
        # Queues for own use
        self.data_queue = Queue.Queue()  # data from stream to write
        self.missed_queue = Queue.Queue()
        # dumps small reports (post-exp and missed values) to master gui
        self.master_gui_dump_queue = master_dump_queue
        self.master_gui_graph_queue = master_graph_queue
        ##########################################################
        # Hardware Parameters
        self.settings = None
        self.ch_num = [0]
        self.scan_freq = 1
        self.n_ch = 1
        self.streamSamplesPerPacket = 25
        self.packetsPerRequest = 48
        self.streamChannelNumbers = self.ch_num
        self.streamChannelOptions = [0] * self.n_ch

    def check_connection(self):
        """Checks if LabJack is ready to be connected to"""
        self.master_gui_dump_queue.put_nowait('<lj>Connecting to LabJack...')
        try:
            self.close()
            self.open()
            self.master_gui_dump_queue.put('<lj>Connected to LabJack!')
            self.connected = True
            return
        except LabJackException:
            try:
                self.streamStop()
                self.close()
                self.open()
                self.master_gui_dump_queue.put('<lj>Connected to LabJack!')
                self.connected = True
                return
            except (LabJackException, LowlevelErrorException):
                try:
                    self.master_gui_dump_queue.put('<lj>Failed. Attempting a Hard Reset...')
                    self.hardReset()
                    time.sleep(2.5)
                    self.open()
                    self.master_gui_dump_queue.put('<lj>Connected to LabJack!')
                    self.connected = True
                    return
                except LabJackException:
                    self.master_gui_dump_queue.put('<lj>** LabJack cannot be reached! '
                                                   'Please reconnect the device.')
                    self.connected = False
                    return

    def reinitialize_vars(self):
        """Reloads channel and freq information from settings
        in case they were changed. call this before any lj streaming"""
        self.ch_num = self.settings.lj_last_used['ch_num']
        self.scan_freq = self.settings.lj_last_used['scan_freq']
        self.n_ch = len(self.ch_num)

    @staticmethod
    def find_packets_per_req(scanFreq, nCh):
        """Returns optimal packets per request to use"""
        if nCh == 7:
            high = 42
        else:
            high = 48
        hold = []
        for i in range(scanFreq + 1):
            if i % 25 == 0 and i % nCh == 0:
                hold.append(i)
        hold = np.asarray(hold)
        hold = min(high, max(hold / 25))
        hold = max(1, hold)
        return hold

    @staticmethod
    def find_samples_per_pack(scanFreq, nCh):
        """Returns optimal samples per packet to use"""
        hold = []
        for i in range(scanFreq + 1):
            if i % nCh == 0:
                hold.append(i)
        return max(hold)

    # noinspection PyDefaultArgument
    def streamConfig(self, NumChannels=1, ResolutionIndex=0,
                     SamplesPerPacket=25, SettlingFactor=0,
                     InternalStreamClockFrequency=0, DivideClockBy256=False,
                     ScanInterval=1, ChannelNumbers=[0],
                     ChannelOptions=[0], ScanFrequency=None,
                     SampleFrequency=None):
        """Sets up Streaming settings"""
        if NumChannels != len(ChannelNumbers) or NumChannels != len(ChannelOptions):
            raise LabJackException("NumChannels must match length "
                                   "of ChannelNumbers and ChannelOptions")
        if len(ChannelNumbers) != len(ChannelOptions):
            raise LabJackException("len(ChannelNumbers) doesn't "
                                   "match len(ChannelOptions)")
        if (ScanFrequency is not None) or (SampleFrequency is not None):
            if ScanFrequency is None:
                ScanFrequency = SampleFrequency
            if ScanFrequency < 1000:
                if ScanFrequency < 25:
                    # below 25 ScanFreq, S/P is some multiple of nCh less than SF.
                    SamplesPerPacket = self.find_samples_per_pack(ScanFrequency, NumChannels)
                DivideClockBy256 = True
                ScanInterval = 15625 / ScanFrequency
            else:
                DivideClockBy256 = False
                ScanInterval = 4000000 / ScanFrequency
        ScanInterval = min(ScanInterval, 65535)
        ScanInterval = int(ScanInterval)
        ScanInterval = max(ScanInterval, 1)
        SamplesPerPacket = max(SamplesPerPacket, 1)
        SamplesPerPacket = int(SamplesPerPacket)
        SamplesPerPacket = min(SamplesPerPacket, 25)
        command = [0] * (14 + NumChannels * 2)
        # command[0] = Checksum8
        command[1] = 0xF8
        command[2] = NumChannels + 4
        command[3] = 0x11
        # command[4] = Checksum16 (LSB)
        # command[5] = Checksum16 (MSB)
        command[6] = NumChannels
        command[7] = ResolutionIndex
        command[8] = SamplesPerPacket
        # command[9] = Reserved
        command[10] = SettlingFactor
        command[11] = (InternalStreamClockFrequency & 1) << 3
        if DivideClockBy256:
            command[11] |= 1 << 1
        t = pack("<H", ScanInterval)
        command[12] = ord(t[0])
        command[13] = ord(t[1])
        for i in range(NumChannels):
            command[14 + (i * 2)] = ChannelNumbers[i]
            command[15 + (i * 2)] = ChannelOptions[i]
        self._writeRead(command, 8, [0xF8, 0x01, 0x11])
        self.streamSamplesPerPacket = SamplesPerPacket
        self.streamChannelNumbers = ChannelNumbers
        self.streamChannelOptions = ChannelOptions
        self.streamConfiged = True
        # Only happens for ScanFreq < 25, in which case
        # this number is generated as described above
        if SamplesPerPacket < 25:
            self.packetsPerRequest = 1
        elif SamplesPerPacket == 25:  # For all ScanFreq > 25.
            self.packetsPerRequest = self.find_packets_per_req(ScanFrequency, NumChannels)
            # Such that PacketsPerRequest*SamplesPerPacket % NumChannels == 0,
            # where min P/R is 1 and max 48 for nCh 1-6,8
            # and max 42 for nCh 7.

    def read_with_counter(self, num_requests, datacount_hold):
        """Given a number of requests, pulls data from labjack
         and returns number of data points pulled"""
        reading = True
        datacount = 0
        while reading:
            if not self.running:
                break
            return_dict = self.streamData(convert=False).next()
            self.data_queue.put_nowait(deepcopy(return_dict))
            datacount += 1
            if datacount >= num_requests:
                reading = False
        datacount_hold.append(datacount)

    # noinspection PyUnboundLocalVariable
    def read_stream_data(self, settings):
        """Reads from stream and puts in queue"""
        # pulls lj config and sets up the stream
        self.settings = settings
        self.reinitialize_vars()
        self.getCalibrationData()
        self.streamConfig(NumChannels=self.n_ch, ChannelNumbers=self.ch_num,
                          ChannelOptions=[0] * self.n_ch, ScanFrequency=self.scan_freq)
        datacount_hold = []
        ttl_time = self.settings.ard_last_used['packet'][3]
        max_requests = int(math.ceil(
            (float(self.scan_freq * self.n_ch * ttl_time / 1000) / float(
                self.packetsPerRequest * self.streamSamplesPerPacket))))
        small_request = int(round(
            (float(self.scan_freq * self.n_ch * 0.5) / float(
                self.packetsPerRequest * self.streamSamplesPerPacket))))
        # We will read 3 segments: 0.5s before begin exp, during exp, and 0.5s after exp
        # 1. wait until arduino and camera are ready
        self.ard_ready_lock.wait()
        self.cmr_ready_lock.wait()
        # 2. notify master gui that we've begun
        self.master_gui_dump_queue.put_nowait('<lj>Started Streaming.')
        ####################################################################
        # STARTED STREAMING
        self.time_start_read = datetime.now()
        # begin the stream; this should happen as close to actual streaming as possible
        # to avoid dropping data
        try:
            self.streamStart()
        except LowlevelErrorException:
            self.streamStop()  # happens if a previous instance was not closed properly
            self.streamStart()
        self.lj_read_ready_lock.set()
        self.running = True
        while self.running:
            # at anytime, this can be disrupted by a hardstop from the main thread
            # 1. 0.5s before exp start; extra collected to avoid missing anything
            self.read_with_counter(small_request, datacount_hold)
            # 2. read for duration of time specified in dirs.settings.ard_last_used['packet'][3]
            self.master_gui_dump_queue.put_nowait('<ljst>')
            self.lj_exp_ready_lock.set()  # we also unblock arduino and camera threads
            time_start = datetime.now()
            self.read_with_counter(max_requests, datacount_hold)
            time_stop = datetime.now()
            # 3. read for another 0.5s after
            self.read_with_counter(small_request, datacount_hold)
            time_stop_read = datetime.now()
            self.running = False
        self.streamStop()
        self.running = False  # redundant but just in case
        if not self.hard_stopped:
            self.master_gui_dump_queue.put_nowait('<lj>Finished Successfully.')
        elif self.hard_stopped:
            self.master_gui_dump_queue.put_nowait('<lj>Terminated Stream.')
            self.hard_stopped = False
        self.lj_read_ready_lock.clear()
        self.lj_exp_ready_lock.clear()
        ####################################################################
        # now we do some reporting
        missed_list_msg = self.missed_queue.get()
        # samples taken for each interval:
        multiplier = self.packetsPerRequest * self.streamSamplesPerPacket
        datacount_hold = (np.asarray(datacount_hold)) * multiplier
        total_samples = sum(i for i in datacount_hold)
        # total run times for each interval
        before_run_time = time_diff(start_time=self.time_start_read, end_time=time_start, choice='micros')
        run_time = time_diff(start_time=time_start, end_time=time_stop, choice='micros')
        after_run_time = time_diff(start_time=time_stop, end_time=time_stop_read, choice='micros')
        total_run_time = time_diff(start_time=self.time_start_read, end_time=time_stop_read, choice='micros')
        # Reconstruct when and where missed values occured
        missed_before, missed_during, missed_after = 0, 0, 0
        if len(missed_list_msg) != 0:
            for i in missed_list_msg:
                if i[1] <= float(int(before_run_time)) / 1000:
                    missed_before += i[0]
                elif float(int(before_run_time)) / 1000 < i[1] <= (float(int(
                        before_run_time)) + float(int(run_time))) / 1000:
                    missed_during += i[0]
                elif (float(int(before_run_time)) + float(int(run_time))) / 1000 < i[1] <= (float(int(
                        before_run_time)) + float(int(run_time)) + float(int(after_run_time))) / 1000:
                    missed_after += i[0]
        missed_total = missed_before + missed_during + missed_after
        # actual sampling frequencies
        try:
            overall_smpl_freq = int(round(float(total_samples) * 1000) / total_run_time)
        except ZeroDivisionError:
            overall_smpl_freq = 0
        overall_scan_freq = overall_smpl_freq / self.n_ch
        try:
            exp_smpl_freq = int(round(float(datacount_hold[1]) * 1000) / run_time)
        except ZeroDivisionError:
            exp_smpl_freq = 0
        exp_scan_freq = exp_smpl_freq / self.n_ch
        self.master_gui_dump_queue.put_nowait('<ljr>{},{},{},{},{},{},{},{},{},{},{},{},n/a,{},n/a,{},n/a,{},n/a,{}'
                                              ''.format(float(before_run_time) / 1000,
                                                        float(run_time) / 1000, float(after_run_time) / 1000,
                                                        float(total_run_time) / 1000,
                                                        datacount_hold[0], datacount_hold[1], datacount_hold[2],
                                                        total_samples, missed_before, missed_during, missed_after,
                                                        missed_total, exp_smpl_freq, overall_smpl_freq, exp_scan_freq,
                                                        overall_scan_freq))

    def data_write_plot(self, results_dir):
        """Reads from data queue and writes to file/plots"""
        self.missed_queue.queue.clear()
        missed_total, missed_list = 0, []
        save_file_name = '[name]--{}'.format(format_daytime(options='daytime'))
        with open(results_dir + save_file_name + '.csv', 'w') as save_file:
            for i in range(self.n_ch):
                save_file.write('AIN{},'.format(self.ch_num[i]))
            save_file.write('\n')
            self.lj_read_ready_lock.wait()  # wait for the go ahead from read_stream_data
            data_to_master_counter = 1
            while self.running:
                if not self.running:
                    self.data_queue.queue.clear()
                    break
                result = self.data_queue.get()
                if result['errors'] != 0:
                    missed_total += result['missed']
                    self.master_gui_dump_queue.put_nowait('<ljm>{}'.format(missed_total))
                    missed_time = datetime.now()
                    timediff = time_diff(start_time=self.time_start_read,
                                         end_time=missed_time)
                    missed_list.append([deepcopy(result['missed']),
                                        deepcopy(float(timediff) / 1000)])
                r = self.processStreamData(result['result'])
                for each in range(len(r['AIN{}'.format(self.ch_num[0])])):
                    for i in range(self.n_ch):
                        save_file.write(str(r['AIN{}'.format(self.ch_num[i])][each]) + ',')
                    save_file.write('\n')
                if time_diff(self.time_start_read) / data_to_master_counter >= 50:
                    to_send = []
                    for i in range(self.n_ch):
                        to_send.append((r['AIN{}'.format(self.ch_num[i])][0]) * (-27) / 5 + (-27) * (i - 1.5))
                    self.master_gui_graph_queue.put_nowait(to_send)
                    data_to_master_counter += 1
                    if not self.running:
                        break
            self.missed_queue.put_nowait(missed_list)


class FireFly(object):
    """firefly camera"""

    def __init__(self, lj_exp_ready_lock, master_gui_queue, cmr_ready_lock, ard_ready_lock):
        # Hardware parameters
        self.context = None
        # Threading controls
        self.lj_exp_ready_lock = lj_exp_ready_lock
        self.cmr_ready_lock = cmr_ready_lock
        self.ard_ready_lock = ard_ready_lock
        self.status_queue = master_gui_queue
        self.data_queue = Queue.Queue()
        ###############################################
        self.connected = False
        self.recording = False
        self.hard_stopped = False
        self.frame = None

    def initialize(self):
        """checks that camera is available"""
        try:
            self.context = fc2.Context()
            self.context.connect(*self.context.get_camera_from_index(0))
            self.context.set_video_mode_and_frame_rate(fc2.VIDEOMODE_640x480Y8,
                                                       fc2.FRAMERATE_30)
            self.context.set_property(**self.context.get_property(fc2.FRAME_RATE))
            self.context.start_capture()
            self.status_queue.put_nowait('<cmr>Connected to Camera!')
            self.connected = True
            return True
        except fc2.ApiError:
            self.status_queue.put_nowait('<cmr>** Camera is not connected or'
                                         ' is occupied by another program. '
                                         'Please disconnect and try again.')
            self.connected = False
            return False

    def camera_run(self):
        """Runs camera non-stop; switches image acquisition method
        from tempImageGet to appendAVI when need to record video"""
        while self.connected:
            if not self.recording:
                try:
                    self.data_queue.put_nowait(self.context.tempImgGet())
                except fc2.ApiError:
                    if dirs.settings.debug_console:
                        print 'Camera Closed. Code = IsoT'
                        return
            if self.recording:
                self.record_video()
            time.sleep(0.031)
            if not self.connected:
                # this means we stopped the experiment and are closing the GUI
                self.close()

    def record_video(self):
        """records video"""
        self.context.openAVI(dirs.results_dir + '[name]--{}.avi'.format(format_daytime(options='daytime')),
                             30, 1000000)
        num_frames = int(dirs.settings.ard_last_used['packet'][3] * 30) / 1000
        self.ard_ready_lock.wait()
        self.cmr_ready_lock.set()
        self.data_queue.put_nowait(self.context.tempImgGet())
        self.lj_exp_ready_lock.wait()
        # started recording
        self.status_queue.put_nowait('<cmr>Started Recording.')
        self.status_queue.put_nowait('<cmrst>')
        self.context.set_strobe_mode(3, True, 1, 0, 10)
        for i in range(num_frames):
            if self.recording:
                self.data_queue.put_nowait(self.context.appendAVI())
            elif not self.recording:
                break
        self.recording = False
        self.context.set_strobe_mode(3, False, 1, 0, 10)
        self.context.closeAVI()
        self.cmr_ready_lock.clear()
        if not self.hard_stopped:
            self.status_queue.put_nowait('<cmr>Finished Successfully.')
        elif self.hard_stopped:
            self.status_queue.put_nowait('<cmr>Terminated Video Recording.')
            self.hard_stopped = False

    def close(self):
        """closes camera instance"""
        self.context.stop_capture()
        self.context.disconnect()


class ArduinoUno(object):
    """Handles serial communication with arduino"""

    def __init__(self, lj_exp_ready_lock, master_gui_queue, ard_ready_lock, cmr_ready_lock):
        # Thread controls
        self.lj_exp_ready_lock = lj_exp_ready_lock
        self.ard_ready_lock = ard_ready_lock
        self.cmr_ready_lock = cmr_ready_lock
        self.status_queue = master_gui_queue
        self.connected = False
        self.running = False
        self.hard_stopped = False
        # Hardware parameters
        self.baudrate = 115200
        self.ser_port = dirs.settings.ser_port
        # Communication protocols
        # Markers are unicode chrs '<' and '>'
        self.start_marker, self.end_marker = 60, 62
        self.serial = None

    def send_to_ard(self, send_str):
        """Sends packed str to arduino"""
        self.serial.write(send_str)

    def get_from_ard(self):
        """Reads serial data from arduino"""
        ard_string = ''
        byte_hold = 'z'
        # We read and discard serial data until we hit '<'
        while ord(byte_hold) != self.start_marker:
            byte_hold = self.serial.read()
            time.sleep(0.00001)
        # Then we read and record serial data until we hit '>'
        while ord(byte_hold) != self.end_marker:
            if ord(byte_hold) != self.start_marker:
                ard_string += byte_hold
            byte_hold = self.serial.read()
        return ard_string

    def send_packets(self, *args):
        """Send experiment config to arduino"""
        for each in args:
            for i in range(len(each)):
                if len(each) > 0:
                    try:
                        get_str = self.get_from_ard()
                        if get_str == 'M':
                            self.send_to_ard(pack(*each[i]))
                    except TypeError:
                        raise serial.SerialException

    @staticmethod
    def list_serial_ports():
        """Finds and returns all available and usable serial ports"""
        if sys.platform.startswith('win'):
            ports = ['COM%s' % (i + 1) for i in range(256)]
        elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
            ports = glob.glob('/dev/tty[A-Za-z]*')
        elif sys.platform.startswith('darwin'):
            ports = glob.glob('/dev/tty.*')
        else:
            raise EnvironmentError('Unsupported platform')
        result = []
        for port in ports:
            try:
                s = serial.Serial(port)
                s.close()
                result.append(port)
            except (OSError, serial.SerialException):
                pass
        return result

    def wait_for_ready(self):
        """Wait for ready message from arduino"""
        msg = ''
        start = datetime.now()
        while msg.find('ready') == -1:
            while self.serial.inWaiting() == 0:
                time.sleep(0.02)
                timediff = time_diff(start)
                if timediff > 3500:
                    return False
            msg = self.get_from_ard()
        if msg == 'ready':
            return True

    def try_serial(self, port):
        """Given a port, attempts to connect to it"""
        try:
            # can we use this port at all?
            self.serial = serial.Serial(port, self.baudrate)
            try:
                # are we able to get the ready message from arduino?
                success = self.wait_for_ready()
                if success:
                    dirs.threadsafe_edit(recipient='ser_port', donor=port)
                    return True
                else:
                    return False
            except IOError:
                return False
        except (serial.SerialException, IOError, OSError):
            try:
                self.serial.close()
                self.serial = serial.Serial(port, self.baudrate)
                try:
                    # are we able to get the ready message from arduino?
                    success = self.wait_for_ready()
                    if success:
                        dirs.threadsafe_edit(recipient='ser_port', donor=port)
                        return True
                    else:
                        return False
                except IOError:
                    return False
            except (serial.SerialException, IOError, OSError, AttributeError):
                return False

    def check_connection(self):
        """Tries every possible serial port"""
        # First we close any outstanding ports
        try:
            self.serial.close()
        except AttributeError:
            pass
        # then we attempt a new connection
        ports = self.list_serial_ports()
        self.status_queue.put('<ard>Connecting to Port '
                              '[{}]...'.format(self.ser_port))
        self.connected = self.try_serial(self.ser_port)
        if self.connected:
            self.status_queue.put('<ard>Success! Connected to Port '
                                  '[{}].'.format(self.ser_port))
            self.connected = True
            return
        elif not self.connected:
            for port in ports:
                if self.try_serial(port):
                    self.ser_port = port
                    dirs.threadsafe_edit(recipient='ser_port', donor=port)
                    self.status_queue.put('<ard>Success! Connected to Port '
                                          '[{}].'.format(self.ser_port))
                    self.connected = True
                    return
                else:
                    self.status_queue.put('<ard>** Failed to connect. '
                                          'Attempting next available Port...')
            self.status_queue.put('<ard>** Arduino cannot be reached! '
                                  'Please make sure the device '
                                  'is plugged in.')
            self.connected = False
            return

    def run_experiment(self):
        """sends data packets and runs experiment"""
        self.status_queue.put_nowait('<ard>Success! Connected to '
                                     'Port [{}]. '
                                     'Sending data '
                                     'packets...'.format(self.ser_port))
        time_offset = 3600 * 4  # EST = -4 hours
        system_time = ["<L", calendar.timegm(time.gmtime()) - time_offset]
        pwm_pack_send = []
        for i in dirs.settings.ard_last_used['pwm_pack']:
            period = (float(1000000) / float(i[4]))
            cycleTimeOn = long(round(period * (float(i[7]) / float(100))))
            cycleTimeOff = long(round(period * (float(1) - (float(i[7]) / float(100)))))
            timePhaseShift = long(round(period * (float(i[6]) / float(360))))
            pwm_pack_send.append(["<LLLLLBL", 0, i[2], i[3], cycleTimeOn, cycleTimeOff,
                                  i[5], timePhaseShift])
        self.send_packets([system_time],
                          [dirs.settings.ard_last_used['packet']],
                          dirs.settings.ard_last_used['tone_pack'],
                          dirs.settings.ard_last_used['out_pack'],
                          pwm_pack_send)
        self.status_queue.put_nowait('<ard>Success! Connected to '
                                     'Port [{}]. '
                                     'Data packets sent'.format(self.ser_port))
        # we're done the bulk of the processing, now we wait for thread stuff
        # this order is very specific! do not modify
        self.ard_ready_lock.set()
        self.cmr_ready_lock.wait()
        self.lj_exp_ready_lock.wait()
        self.send_to_ard(pack("<B", 1))
        start = datetime.now()
        self.status_queue.put_nowait('<ard>Started Procedure.')
        self.status_queue.put_nowait('<ardst>')
        total_time = dirs.settings.ard_last_used['packet'][3]
        self.running = True
        while self.running:
            if not self.running:
                break
            if time_diff(start) >= total_time:
                end_msg = self.get_from_ard()
                end_msg = end_msg.split(',')
                self.status_queue.put_nowait('<ard>Finished. Hardware report: '
                                             'procedure was exactly [{} ms], '
                                             'from [{}] to [{}]'
                                             ''.format(end_msg[0], end_msg[1], end_msg[2]))
                self.running = False
                break
            time.sleep(0.1)
        self.running = False
        if self.hard_stopped:
            self.status_queue.put_nowait('<ard>Terminated Procedure.')
            self.hard_stopped = False
        self.serial.close()
        self.serial.open()
        self.serial.close()
        self.ard_ready_lock.clear()


#################################################################
# Directories and Saves
class Directories(object):
    """File Formats:
    .frcl: Main Settings Pickle
    .csv: Standard comma separated file for data output"""

    def __init__(self):
        self.lock = threading.Lock()
        self.user_home = os.path.expanduser('~')
        self.main_save_dir = self.user_home + '/desktop/frCntrlSaves/'
        self.results_dir = ''
        self.save_on_exit = True
        self.settings = MainSettings()
        if not os.path.isfile(self.user_home + '/frSettings.frcl'):
            # Create Settings file if does not exist
            with open(self.user_home + '/frSettings.frcl', 'wb') as f:
                # Put in some example settings and presets
                self.settings.load_examples()
                pickle.dump(self.settings, f)
        if not os.path.exists(self.main_save_dir):
            os.makedirs(self.main_save_dir)

    def load(self):
        """Load last used settings"""
        with open(self.user_home + '/frSettings.frcl', 'rb') as settings_file:
            self.settings = pickle.load(settings_file)
            self.check_dirs()

    def save(self):
        """Save settings for future use"""
        with open(self.user_home + '/frSettings.frcl', 'wb') as settings_file:
            pickle.dump(self.settings, settings_file)

    def check_dirs(self):
        """Creates a save directory named in our Last Used Dir. records
        if that directory does not exist"""
        if self.settings.save_dir != '':
            if not os.path.isdir(self.main_save_dir + self.settings.save_dir):
                os.makedirs(self.main_save_dir + self.settings.save_dir)

    def clear_saves(self):
        """Removes settings and save directories"""
        shutil.rmtree(self.user_home + '/desktop/frCntrlSaves/')
        os.remove(self.user_home + '/frSettings.frcl')

    def threadsafe_edit(self, recipient, donor, name=None):
        """Edits settings in a threadsafe manner"""
        self.lock.acquire()
        if recipient == 'ser_port':
            self.settings.ser_port = donor
        elif recipient == 'save_dir':
            self.settings.save_dir = donor
        elif recipient == 'fp_last_used':
            self.settings.fp_last_used = donor
        elif recipient == 'lj_last_used':
            self.settings.lj_last_used = donor
        elif recipient == 'ard_last_used':
            self.settings.ard_last_used = donor
        elif recipient == 'lj_presets':
            self.settings.lj_presets[name] = donor
        elif recipient == 'ard_presets':
            self.settings.ard_presets[name] = donor
        else:
            raise AttributeError('Settings has no attribute called {}!'.format(recipient))
        self.lock.release()


class MainSettings(object):
    """Object saves and holds all relevant parameters and presets"""

    def __init__(self):
        self.ser_port = ''
        self.save_dir = ''
        self.fp_last_used = {'ch_num': [],
                             'main_freq': 0,
                             'isos_freq': 0}
        self.lj_last_used = {'ch_num': [],
                             'scan_freq': 0}
        self.ard_last_used = {'packet': [],
                              'tone_pack': [],
                              'out_pack': [],
                              'pwm_pack': []}
        self.lj_presets = {}
        self.ard_presets = {}
        self.debug_console = False

    def load_examples(self):
        """Example settings"""
        if sys.platform.startswith('win'):
            self.ser_port = 'COM4'
        else:
            self.ser_port = '/dev/tty.usbmodem1421'
        self.fp_last_used = {'ch_num': [3, 4, 5],
                             'main_freq': 211,
                             'isos_freq': 531}
        self.lj_last_used = {'ch_num': [0, 1, 2],
                             'scan_freq': 6250}
        self.ard_last_used = {'packet': ['<BBLHHH', 0, 0, 20000, 0, 0, 0],
                              'tone_pack': [],
                              'out_pack': [],
                              'pwm_pack': []}
        # A few example presets for the first load
        self.lj_presets = {'example': {'ch_num': [0, 1, 2, 10, 11],
                                       'scan_freq': 6250}}
        self.ard_presets = {'example':
                            {'packet': ['<BBLHHH', 255, 255, 180000, 1, 2, 0],
                             'tone_pack': [['<LLH', 120000, 150000, 2800]],
                             'out_pack': [['<LB', 148000, 4], ['<LB', 150000, 4]],
                             'pwm_pack': []}}
        self.debug_console = False

    def quick_ard(self):
        """
        Quickly returns all Arduino parameters
        """
        return [self.ard_last_used['packet'],
                self.ard_last_used['tone_pack'],
                self.ard_last_used['out_pack'],
                self.ard_last_used['pwm_pack']]

    def quick_lj(self):
        """
        Quickly return all LabJack parameters
        """
        return [self.lj_last_used['ch_num'],
                self.lj_last_used['scan_freq']]

    def quick_fp(self):
        """
        Quickly return all Photometry parameters
        """
        return [self.fp_last_used['ch_num'],
                self.fp_last_used['main_freq'],
                self.fp_last_used['isos_freq']]


#################################################################
#################################################################
if __name__ == '__main__':

    # Open Tkinter instance
    tcl_main_root = Tk.Tk()

    # Setup all Directories
    dirs = Directories()
    # Load last used settings
    dirs.load()

    # Run Main Loop
    main = MasterGUI(tcl_main_root)
    main.master.mainloop()

    # Save Settings for Next Run
    if dirs.save_on_exit:
        dirs.save()
#################################################################
