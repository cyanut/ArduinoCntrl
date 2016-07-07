"""
For use with LabJack U6 and PTGrey FMVU-03MTC-CS
"""
import serial
import time
import os
import glob
import threading
import copy
import math
import calendar
import Queue
import pickle
from struct import *
from datetime import datetime
from operator import itemgetter
from pprint import pprint
import shutil
# noinspection PyUnresolvedReferences
import sys

import numpy as np
import Tkinter as Tk
import tkMessageBox as tkMb
import tkFont
import Pmw
import LabJackPython
import u6
# import flycapture2a as fc2

################################################################
# To do list:
# - Arduino GUI Geometry fine tuning
# - Arduino optiboot.c loader: remove led flash on start?
#################################################################
# Global Variables
NUM_LJ_CH = 14
SAVE_ON_EXIT = True
TIME_OFFSET = 3600*4  # EST = -4 hours.


# Misc. Functions
def min_from_sec(secs, ms=False, option=None):
    """
    Turns Seconds into MM:SS
    :param secs: seconds
    :param ms: Boolean (return ms as well?)
    :param option: String (min only, sec only)
    :return:
        String
    """
    output = None
    sec = int(secs) % 60
    mins = int(secs)//60
    if ms:
        millis = int((secs - int(secs))*1000)
        output = '{:0>2}:{:0>2}.{:0>3}'.format(mins, sec, millis)
    elif not ms:
        output = '{:0>2}:{:0>2}'.format(mins, sec)
    if option == 'min':
        output = '{:0>2}'.format(mins)
    elif option == 'sec':
        output = '{:0>2}'.format(sec)
    return output


def get_time_diff(start_time, end_time=None, choice='ms'):
    """
    Returns time difference from starting time
    """
    if end_time is None:
        end_time = datetime.now()
    timediff = (end_time-start_time)
    if choice == 'ms':
        return timediff.seconds*1000+timediff.microseconds/1000
    elif choice == 'us':
        return timediff.seconds*1000+float(timediff.microseconds)/1000


def get_day(options=0):
    """
    Returns day and time in various formats
    :return:
        String
    """
    i = datetime.now()
    hour = '{:0>2}'.format(i.hour)
    minute = '{:0>2}'.format(i.minute)
    second = '{:0>2}'.format(i.second)
    if options == 0 or options == 'day':
        return '%s/%s/%s' % (i.year, i.month, i.day)
    elif options == 1 or options == 'daytime':
        return '%s-%s-%s [%s-%s-%s]' % (i.year, i.month, i.day,
                                        hour, minute, second)
    elif options == 2 or options == 'day2':
        return '%s-%s-%s' % (i.year, i.month, i.day)
    elif options == 3 or options == 'time':
        if i.hour > 12:
            hour = str(i.hour-12)+'pm'
        if i.hour == 12:
            hour = '12pm'
        if i.hour < 12:
            hour = str(i.hour)+'am'
        if i.hour == 0:
            hour = '12am'
        return '%s-%s-%s' % (hour, minute, second)


def check_binary(num, register):
    """
    Given a number and arduino register
    return the correct list of arduino pins
    :param num: number
    :param register: arduino register B or D
    :return:
        List
    """
    dicts = {}
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


def deep_copy_lists(outer, inner):
    """
    Creates a list of lists, each with unique python IDs
    """
    hold = []
    for i in range(outer):
        hold.append(copy.deepcopy([copy.deepcopy([])]*inner))
    return hold


def limit_string_length(string, length):
    """
    Limit a given string to a specified length
    """
    if len(string) <= length:
        return string
    else:
        return string[:length-3]+'...'


def list_serial_ports():
    """
    Finds and returns all available and open serial ports
    :return:
     List
    """
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


def pin_to_int(pin):
    """
    Returns the integer representation of
    any given arduino pin
    """
    if pin < 8:
        return int('1' + '0' * int(pin), 2)
    if 8 <= pin <= 13:
        return int('1' + '0' * (int(pin) - 8), 2)


def dict_flatten(*args):
    """
    flattens the given dictionary into a list
    """
    hold = []
    for a in args:
        hold.append([i for s in a.values() for i in s])
    return hold


#################################################################
# GUIs
# noinspection PyAttributeOutsideInit
class MasterGUI(object):
    """
    Main Program GUI. Launch everything from here
    """
    def __init__(self, master):
        self.single_widget_dim = 100
        self.master = master
        self.master.title('Fear Control')
        self.master.resizable(width=False, height=False)
        self.time_label_font = tkFont.Font(family='Arial', size=8)
        self.label_font = tkFont.Font(family='Arial', size=10)
        self.label_font_symbol = tkFont.Font(family='Arial', size=9)
        # noinspection PyUnresolvedReferences
        self.balloon = Pmw.Balloon(master)
        self.results_dir_used = {}
        self.make_save_dir = 0
        self.save_dir_name_used = []
        self.ALL = Tk.N + Tk.E + Tk.S + Tk.W
        self.ttl_time = dirs.settings.ard_last_used['packet'][3]
        self.master.protocol('WM_DELETE_WINDOW', self.hard_exit)
        # Threading control and devices
        self.master_queue = Queue.Queue()
        self.ard_queue = Queue.Queue()
        self.ard_ser = None
        self.lj_queue = Queue.Queue()
        self.lj_instance = None
        self.lj_connected = False
        self.lj_device = None
        #########################################
        # Give each setup GUI its own box
        #########################################
        # Photometry Config
        # Frame
        photometry_frame = Tk.LabelFrame(self.master,
                                         text='Optional Photometry Config.',
                                         width=self.single_widget_dim*2,
                                         height=self.single_widget_dim,
                                         highlightthickness=5)
        photometry_frame.grid(row=0, column=0, sticky=self.ALL)
        # Variables
        self.fp_bool = Tk.IntVar()
        self.fp_bool.set(0)
        self.fp_str_var = Tk.StringVar()
        self.fp_str_var.set('\n[N/A]\n')
        # Buttons
        self.fp_checkbutton = Tk.Checkbutton(photometry_frame,
                                             text='Toggle Photometry On/Off',
                                             variable=self.fp_bool,
                                             onvalue=1, offvalue=0,
                                             command=self.fp_toggle)
        self.fp_checkbutton.pack()
        self.start_gui_button = Tk.Button(photometry_frame,
                                          text='CONFIG',
                                          command=self.fp_config)
        self.start_gui_button.pack()
        self.start_gui_button.config(state='disabled')
        Tk.Label(photometry_frame, textvariable=self.fp_str_var).pack()
        #########################################
        # Save File Config
        self.save_grab_list()
        # Primary Save Frame
        save_frame = Tk.LabelFrame(self.master,
                                   text='Data Output Save Location',
                                   width=self.single_widget_dim*2,
                                   height=self.single_widget_dim,
                                   highlightthickness=5,
                                   highlightcolor='white')
        save_frame.grid(row=1, column=0,
                        columnspan=1,
                        sticky=self.ALL)
        # Display Save Name Chosen
        self.save_file_name = Tk.StringVar()
        save_file_label = Tk.Label(save_frame,
                                   textvariable=self.save_file_name,
                                   relief=Tk.RAISED)
        save_file_label.pack(side=Tk.TOP, expand='yes', fill='both')
        # Secondary Save Frame: Existing Saves
        existing_frame = Tk.LabelFrame(save_frame,
                                       text='Select a Save Name')
        existing_frame.pack(fill='both', expand='yes')
        self.dir_chosen = Tk.StringVar()
        self.save_file_name.set('Last Used Save Dir.:'
                                '\n[{}]'.format(limit_string_length(dirs.settings.save_dir.upper(),
                                                                    20)))
        self.dir_chosen.set('{: <25}'.format(dirs.settings.save_dir))
        if len(self.save_dir_list) == 0:
            self.save_dir_menu = Tk.OptionMenu(existing_frame,
                                               self.dir_chosen,
                                               ' '*15)
        else:
            self.save_dir_menu = Tk.OptionMenu(existing_frame,
                                               self.dir_chosen,
                                               *self.save_dir_list,
                                               command=lambda path:
                                               self.save_button_options(inputs=path))
        self.save_dir_menu.config(width=20)
        self.save_dir_menu.grid(sticky=self.ALL, columnspan=2)
        # Secondary Save Frame: New Saves
        new_frame = Tk.LabelFrame(save_frame, text='Create a New Save Location')
        new_frame.pack(fill='both', expand='yes')
        self.new_save_entry = Tk.Entry(new_frame)
        self.new_save_entry.pack(side=Tk.TOP)
        self.new_save_button = Tk.Button(new_frame,
                                         text='Create New',
                                         command=lambda:
                                         self.save_button_options(new=True))
        self.new_save_button.pack(side=Tk.TOP)
        #########################################
        # LabJack Config
        # Frame
        lj_frame = Tk.LabelFrame(self.master,
                                 text='LabJack Config.',
                                 width=self.single_widget_dim*2,
                                 height=self.single_widget_dim,
                                 highlightthickness=5)
        lj_frame.grid(row=2, column=0, sticky=self.ALL)
        # Variables
        self.lj_str_var = Tk.StringVar()
        channels = dirs.settings.lj_last_used['ch_num']
        freq = dirs.settings.lj_last_used['scan_freq']
        self.lj_str_var.set('Channels:\n'
                            '{}\n\n'
                            'Scan Freq: '
                            '[{}Hz]'.format(channels, freq))
        # Current State Report
        Tk.Label(lj_frame, textvariable=self.lj_str_var).pack(side=Tk.TOP)
        # Config Button
        self.lj_config_button = Tk.Button(lj_frame,
                                          text='CONFIG',
                                          command=self.lj_config)
        self.lj_config_button.pack(side=Tk.BOTTOM, expand=True)
        #########################################
        # Arduino Config
        # Frame
        self.ard_preset_list = []
        self.ard_bckgrd_height = 260
        ard_frame = Tk.LabelFrame(self.master,
                                  text='Arduino Stimuli Config.',
                                  width=self.single_widget_dim*11,
                                  height=self.ard_bckgrd_height)
        ard_frame.grid(row=0,
                       rowspan=3,
                       column=1,
                       sticky=self.ALL)
        Tk.Label(ard_frame,
                 text='Last used settings shown. '
                      'Click then rollover individual segments for '
                      'specific stimuli config information.',
                 relief=Tk.RAISED).grid(row=0,
                                        columnspan=55,
                                        sticky=self.ALL)
        # Debug Buttons
        self.debug_button = Tk.Button(ard_frame, text='DEBUG',
                                      command=self.gui_debug)
        self.debug_button.grid(row=0, column=80, columnspan=10, sticky=self.ALL)
        self.clr_svs_button = Tk.Button(ard_frame, text='ClrSvs',
                                        command=lambda:
                                        dirs.clear_saves(self.master))
        self.clr_svs_button.grid(row=0, column=90, columnspan=10, sticky=self.ALL)
        # Main Progress Canvas
        self.ard_canvas = Tk.Canvas(ard_frame,
                                    width=1050,
                                    height=self.ard_bckgrd_height+10)
        self.ard_canvas.grid(row=1,
                             column=0,
                             columnspan=100)
        self.gui_canvas_init()
        # Progress Bar Control Buttons
        bs_row = 5
        self.prog_on = Tk.Button(ard_frame,
                                 text='START')
        self.prog_on.grid(row=bs_row,
                          column=4,
                          stick=self.ALL)
        self.prog_off = Tk.Button(ard_frame,
                                  text='STOP')
        self.prog_off.grid(row=bs_row+1,
                           column=4,
                           stick=self.ALL)
        # Grab Data and Generate Progress Bar
        self.ard_grab_data()
        # Arduino Presets
        as_row = 7
        self.ard_update_preset_list()
        self.ard_preset_chosen = Tk.StringVar()
        self.ard_preset_chosen.set('{: <40}'.format('(select a preset)'))
        self.ard_preset_menu = Tk.OptionMenu(ard_frame,
                                             self.ard_preset_chosen,
                                             *self.ard_preset_list,
                                             command=lambda file_in:
                                             self.ard_grab_data(True, file_in))
        self.ard_preset_menu.grid(row=as_row,
                                  column=0,
                                  columnspan=4,
                                  sticky=self.ALL)
        self.ard_preset_menu.config(width=10)
        # Manual Arduino Setup
        # Total Experiment Time Config
        ts_row = 3
        Tk.Label(ard_frame, text='MM',
                 font=self.time_label_font).grid(row=ts_row, column=1, sticky=self.ALL)

        Tk.Label(ard_frame, text='SS',
                 font=self.time_label_font).grid(row=ts_row, column=3, sticky=self.ALL)
        Tk.Label(ard_frame,
                 text='Total Experiment Time:').grid(row=ts_row+1,
                                                     column=0,
                                                     sticky=self.ALL)
        # Minutes
        self.min_entry = Tk.Entry(ard_frame, width=2)
        self.min_entry.grid(row=ts_row+1, column=1, sticky=self.ALL)
        self.min_entry.insert(Tk.END,
                              '{}'.format(min_from_sec(self.ttl_time/1000, option='min')))
        Tk.Label(ard_frame, text=':').grid(row=ts_row+1, column=2, sticky=self.ALL)
        # Seconds
        self.sec_entry = Tk.Entry(ard_frame, width=2)
        self.sec_entry.grid(row=ts_row+1, column=3, sticky=self.ALL)
        self.sec_entry.insert(Tk.END,
                              '{}'.format(min_from_sec(self.ttl_time/1000,
                                                       option='sec')))
        self.ard_time_confirm = Tk.Button(ard_frame, text='Confirm',
                                          command=self.ard_get_time)
        self.ard_time_confirm.grid(row=ts_row+1, column=4, sticky=Tk.W)
        # Tone Config
        self.tone_setup = Tk.Button(ard_frame, text='Tone Setup',
                                    command=lambda types='tone':
                                    self.ard_config(types))
        self.tone_setup.grid(row=5, column=0, sticky=self.ALL)
        self.out_setup = Tk.Button(ard_frame, text='PWM Setup',
                                   command=lambda types='pwm':
                                   self.ard_config(types))
        self.out_setup.grid(row=5, column=1, columnspan=3, sticky=self.ALL)
        self.pwm_setup = Tk.Button(ard_frame, text='Simple Outputs',
                                   command=lambda types='output':
                                   self.ard_config(types))
        self.pwm_setup.grid(row=6, column=0, sticky=self.ALL)
        # Status messages for devices
        Tk.Label(ard_frame, text='Devices:  ', relief=Tk.RAISED).grid(row=0,
                                                                      column=60,
                                                                      columnspan=10,
                                                                      sticky=self.ALL)
        # arduino
        self.ard_status = Tk.StringVar()
        Tk.Label(ard_frame, anchor=Tk.E, text='Arduino Status:  ').grid(row=4,
                                                                        column=10,
                                                                        columnspan=15,
                                                                        sticky=self.ALL)
        ard_status_display = Tk.Label(ard_frame, anchor=Tk.W,
                                      textvariable=self.ard_status,
                                      relief=Tk.SUNKEN)
        ard_status_display.grid(row=4, column=25, columnspan=70, sticky=self.ALL)
        self.ard_status.set('null')
        self.ard_toggle_var = Tk.IntVar()
        self.ard_toggle_var.set(1)
        self.ard_toggle_button = Tk.Checkbutton(ard_frame, variable=self.ard_toggle_var, text='Arduino',
                                                onvalue=1, offvalue=0,
                                                command=lambda:
                                                self.device_status_msg_toggle(self.ard_toggle_var,
                                                                              self.ard_status,
                                                                              ard_status_display))
        self.ard_toggle_button.grid(row=0, column=70, sticky=Tk.E)
        # LabJack
        self.lj_status = Tk.StringVar()
        Tk.Label(ard_frame, anchor=Tk.E, text='LabJack Status:  ').grid(row=5,
                                                                        column=10,
                                                                        columnspan=15,
                                                                        sticky=self.ALL)
        lj_status_display = Tk.Label(ard_frame, anchor=Tk.W,
                                     textvariable=self.lj_status,
                                     relief=Tk.SUNKEN)
        lj_status_display.grid(row=5, column=25, columnspan=70, sticky=self.ALL)
        self.lj_status.set('null')
        self.lj_toggle_var = Tk.IntVar()
        self.lj_toggle_var.set(1)
        self.lj_toggle_button = Tk.Checkbutton(ard_frame, variable=self.lj_toggle_var, text='LabJack',
                                               onvalue=1, offvalue=0,
                                               command=lambda:
                                               self.device_status_msg_toggle(self.lj_toggle_var,
                                                                             self.lj_status,
                                                                             lj_status_display))
        self.lj_toggle_button.grid(row=0, column=72, sticky=Tk.E)
        # Camera
        self.cmr_toggle_var = Tk.IntVar()
        self.cmr_toggle_var.set(1)
        self.cmr_toggle_button = Tk.Checkbutton(ard_frame, variable=self.cmr_toggle_var, text='Camera',
                                                onvalue=1, offvalue=0)
        self.cmr_toggle_button.grid(row=0, column=74, sticky=Tk.E)
        # Update Window
        self.gui_update_window()

    # General GUI Functions
    def gui_canvas_init(self):
        """
        Setup Progress bar Canvas
        """
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

    def gui_update_window(self):
        """
        Update GUI Idle tasks, and centers
        """
        self.master.update_idletasks()
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        [window_width, window_height] = list(int(i) for i in
                                             self.master.geometry().split('+')[0].split('x'))
        x_pos = screen_width / 2 - window_width / 2
        y_pos = screen_height / 2 - window_height / 2
        self.master.geometry('{}x{}+{}+{}'.format(window_width,
                                                  window_height,
                                                  x_pos, y_pos))

    @staticmethod
    def gui_debug():
        """
        Under the hood stuff here
        """
        print '#'*40+'DEBUG\n\n'
        print 'SETTINGS'
        pprint(vars(dirs.settings))
        print '#'*15
        print 'ACTIVE THREADS'
        print threading.active_count()

    def hard_exit(self, allow=True):
        """
        Handles threads first before exiting for a clean close
        """
        if allow:
            self.master.destroy()
            self.master.quit()
        else:
            tkMb.showwarning('Error!',
                             'Please STOP the experiment first.',
                             parent=self.master)

    def gui_queue_process(self, queue, success_msg, fail_msg,
                          success_fn=None, fail_fn=None,
                          header='<no_header>', header_var=None,
                          rate=100):
        """
        Processes queues passed to threads
        """
        rerun = False
        try:
            queue_msg = queue.get(0)
            if queue_msg.startswith(header):
                header_var.set(queue_msg.replace(header, ''))
                rerun = True
            elif queue_msg in success_msg:
                success_msg.remove(queue_msg)
                if len(success_msg) == 0:
                    if success_fn is not None:
                        success_fn()
                    else:
                        self.master_queue.put(queue_msg)
                else:
                    rerun = True
            elif queue_msg in fail_msg:
                if fail_fn is not None:
                    fail_fn()
                else:
                    self.master_queue.put(fail_msg[0])
        except Queue.Empty:
            if len(success_msg) == 0:
                success_fn()
            else:
                rerun = True
        if rerun:
            self.master.after(rate, lambda:
                              self.gui_queue_process(queue=queue,
                                                     success_msg=success_msg,
                                                     fail_msg=fail_msg,
                                                     success_fn=success_fn,
                                                     fail_fn=fail_fn,
                                                     header=header, header_var=header_var,
                                                     rate=rate))

    @staticmethod
    def device_status_msg_toggle(var, status, display):
        """
        Hides or displays device statuses depending on
         toggle state
        """
        if var.get() == 0:
            status.set('disabled')
            display.config(state=Tk.DISABLED)
        elif var.get() == 1:
            status.set('enabled')
            display.config(state=Tk.NORMAL)

    # Save Functions
    def save_grab_list(self):
        """
        Updates output save directories list
        """
        self.save_dir_list = [d for d
                              in os.listdir(dirs.main_save_dir)
                              if os.path.isdir(dirs.main_save_dir+d)]

    def save_button_options(self, inputs=None, new=False):
        """
        Determines whether to make a new save folder or not
        """
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
                self.dir_chosen.set(self.save_dir_to_use)
                menu.add_command(label=self.save_dir_to_use,
                                 command=lambda path=self.save_dir_to_use:
                                 self.save_button_options(inputs=path))
                self.save_dir_name_used.append(self.save_dir_to_use)
        else:
            ready = 1
            self.dir_chosen.set(inputs)
            self.save_dir_to_use = str(self.dir_chosen.get())
        if ready == 1:
            self.preresults_dir = str(dirs.main_save_dir)+self.save_dir_to_use+'/'
            if self.preresults_dir not in self.results_dir_used:
                dirs.results_dir = self.preresults_dir+'{} at [{}]/'.format(get_day(2), get_day(3))
                self.make_save_dir = 1
            else:
                dirs.results_dir = self.results_dir_used[self.preresults_dir]
                self.make_save_dir = 0
            self.save_file_name.set(
                'Currently Selected:\n[{}]'.format(
                    limit_string_length(self.save_dir_to_use.upper(), 20)
                )
            )
            dirs.settings.save_dir = self.save_dir_to_use

    # LabJack Functions
    def lj_config(self):
        """
        Opens LJ GUI for settings config
        """
        config = Tk.Toplevel(self.master)
        config_run = LabJackGUI(config)
        config_run.run()
        channels, freq = dirs.settings.quick_lj()
        self.lj_str_var.set('Channels:\n{}\n'
                            '\nScan Freq: [{}Hz]'.format(channels, freq))

    # Photometry Functions
    def fp_toggle(self):
        """
        Toggles Photometry options On or Off
        """
        if self.fp_bool.get() == 1:
            self.start_gui_button.config(state=Tk.NORMAL)
            ch_num, main_freq, isos_freq = dirs.settings.quick_fp()
            state = 'Channels: {}\nMain Freq: {}Hz\nIsos Freq: {}Hz'.format(ch_num,
                                                                            main_freq,
                                                                            isos_freq)
            self.fp_str_var.set(state)
        elif self.fp_bool.get() == 0:
            self.start_gui_button.config(state=Tk.DISABLED)
            self.fp_str_var.set('\n[N/A]\n')

    def fp_config(self):
        """
        Configures photometry options
        """
        config = Tk.Toplevel(self.master)
        config_run = PhotometryGUI(config)
        config_run.run()
        state = 'Channels: {}\nMain Freq: ' \
                '{}Hz\nIsos Freq: {}Hz'.format(config_run.ch_num,
                                               config_run.stim_freq['main'],
                                               config_run.stim_freq['isos'])
        self.fp_str_var.set(state)

    # Arduino Functions
    def ard_config(self, types):
        """
        Presents the requested Arduino GUI
        """
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
        if not config_run.hard_stop:
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
        """
        Gets total exp time from GUI input
        """
        try:
            # Grab Inputs
            mins = int(self.min_entry.get().strip())
            secs = int(self.sec_entry.get().strip())
            mins += secs//60
            secs %= 60
            # Update Fields if improper format entered
            self.min_entry.delete(0, Tk.END)
            self.min_entry.insert(Tk.END, '{:0>2}'.format(mins))
            self.sec_entry.delete(0, Tk.END)
            self.sec_entry.insert(Tk.END, '{:0>2}'.format(secs))
            # Update Vairbales
            self.ttl_time = (mins*60+secs)*1000
            dirs.settings.ard_last_used['packet'][3] = self.ttl_time
            self.ard_grab_data(destroy=True)
        except ValueError:
            tkMb.showinfo('Error!',
                          'Time must be entered as integers',
                          parent=self.master)

    def ard_update_preset_list(self):
        """
        List of all Arduino Presets
        """
        self.ard_preset_list = [i for i in dirs.settings.ard_presets]

    def ard_grab_data(self, destroy=False, load=False):
        """
        Obtain arduino data from saves
        """
        # If load is false, then we load from settings.frcl
        if load is not False:
            # Then load must be a preset name.
            dirs.settings.ard_last_used = copy.deepcopy(dirs.settings.ard_presets[load])
            # Update Total Time Fields
            last_used_time = dirs.settings.ard_last_used['packet'][3]/1000
            self.min_entry.delete(0, Tk.END)
            self.sec_entry.delete(0, Tk.END)
            self.min_entry.insert(Tk.END, '{}'.format(min_from_sec(last_used_time,
                                                                   option='min')))
            self.sec_entry.insert(Tk.END, '{}'.format(min_from_sec(last_used_time,
                                                                   option='sec')))
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
        self.ard_data = ArduinoGUI(Tk.Toplevel())
        self.ard_data.root.destroy()
        divisor = 5+5*int(self.ard_data.packet[3]/300000)
        segment = float(self.ard_data.packet[3]/1000)/divisor
        self.v_bars = [[]]*(1+int(round(segment)))
        self.bar_times = [[]]*(1+int(round(segment)))
        for i in range(int(round(segment))):
            if i > 0:
                if i % 2 != 0:
                    self.v_bars[i] = self.ard_canvas.create_rectangle(i*(1000.0/segment)-1,
                                                                      15,
                                                                      i*(1000.0/segment)+1,
                                                                      self.ard_bckgrd_height-5,
                                                                      fill='white')
                if i % 2 == 0:
                    self.v_bars[i] = self.ard_canvas.create_rectangle(i*(1000.0/segment)-1,
                                                                      15,
                                                                      i*(1000.0/segment)+1,
                                                                      self.ard_bckgrd_height,
                                                                      fill='white')
                    self.bar_times[i] = self.ard_canvas.create_text(i*(1000.0/segment),
                                                                    self.ard_bckgrd_height+8,
                                                                    text=min_from_sec(divisor*i),
                                                                    fill='black',
                                                                    font=self.time_label_font)
                if i == int(round(segment))-1 and (i+1) % 2 == 0 and (i+1)*(1000.0/segment) <= 1001:
                    if round((i+1)*(1000.0/segment)) != 1000.0:
                        self.v_bars[i+1] = self.ard_canvas.create_rectangle((i+1)*(1000.0/segment)-1,
                                                                            15,
                                                                            (i+1)*(1000.0/segment)+1,
                                                                            self.ard_bckgrd_height,
                                                                            fill='white')
                    elif round((i+1)*(1000.0/segment)) == 1000:
                        self.v_bars[i+1] = self.ard_canvas.create_rectangle((i+1)*(1000.0/segment)-1,
                                                                            self.ard_bckgrd_height-5,
                                                                            (i+1)*(1000.0/segment)+1,
                                                                            self.ard_bckgrd_height,
                                                                            fill='white')
                    self.bar_times[i+1] = self.ard_canvas.create_text((i+1)*(1000.0/segment),
                                                                      self.ard_bckgrd_height+8,
                                                                      text=min_from_sec(divisor*(i+1)),
                                                                      fill='black',
                                                                      font=self.time_label_font)
                if i == int(round(segment))-1 and (i+1) % 2 != 0 and (i+1)*(1000.0/segment) <= 1001:
                    if round((i+1)*(1000.0/segment)) != 1000.0:
                        self.v_bars[i+1] = self.ard_canvas.create_rectangle((i+1)*(1000.0/segment)-1,
                                                                            15,
                                                                            (i+1)*(1000.0/segment)+1,
                                                                            self.ard_bckgrd_height,
                                                                            fill='white')
                    elif round((i+1)*(1000.0/segment)) == 1000:
                        self.v_bars[i+1] = self.ard_canvas.create_rectangle((i+1)*(1000.0/segment)-1,
                                                                            self.ard_bckgrd_height-5,
                                                                            (i+1)*(1000.0/segment)+1,
                                                                            self.ard_bckgrd_height,
                                                                            fill='white')
        self.tone_data, self.out_data, self.pwm_data = -1, -1, -1
        self.tone_bars = []
        if len(self.ard_data.tone_pack) != 0:
            self.tone_data = self.ard_decode_data('tone', self.ard_data.tone_pack)
            self.tone_bars = [[]]*len(self.tone_data)
            for i in range(len(self.tone_data)):
                self.tone_bars[i] = self.ard_canvas.create_rectangle(self.tone_data[i][0],
                                                                     0+15,
                                                                     self.tone_data[i][1]+self.tone_data[i][0],
                                                                     35, fill='yellow', outline='blue')
                self.balloon.tagbind(self.ard_canvas,
                                     self.tone_bars[i],
                                     '{} - {}\n{} Hz'.format(
                                         min_from_sec(
                                             self.tone_data[i][4]/1000),
                                         min_from_sec(
                                             self.tone_data[i][5]/1000),
                                         self.tone_data[i][3]))
        self.out_bars = []
        if len(self.ard_data.out_pack) != 0:
            pin_ids = range(2, 8)
            self.out_data = self.ard_decode_data('output',
                                                 self.ard_data.out_pack)
            self.out_bars = [[]]*len(self.out_data)
            for i in range(len(self.out_data)):
                y_pos = 35+(pin_ids.index(self.out_data[i][3]))*20
                self.out_bars[i] = self.ard_canvas.create_rectangle(self.out_data[i][0],
                                                                    y_pos,
                                                                    self.out_data[i][1]+self.out_data[i][0],
                                                                    y_pos+20,
                                                                    fill='yellow', outline='blue')
                self.balloon.tagbind(self.ard_canvas,
                                     self.out_bars[i],
                                     '{} - {}\nPin {}'.format(
                                         min_from_sec(
                                             self.out_data[i][4]/1000),
                                         min_from_sec(
                                             self.out_data[i][5]/1000),
                                         self.out_data[i][3]))
        self.pwm_bars = []
        if len(self.ard_data.pwm_pack) != 0:
            pin_ids = range(8, 14)
            pin_ids.remove(10)
            self.pwm_data = self.ard_decode_data('pwm', self.ard_data.pwm_pack)
            self.pwm_bars = [[]]*len(self.pwm_data)
            for i in range(len(self.pwm_data)):
                y_pos = 155+(pin_ids.index(self.pwm_data[i][3]))*20
                self.pwm_bars[i] = self.ard_canvas.create_rectangle(self.pwm_data[i][0],
                                                                    y_pos,
                                                                    self.pwm_data[i][1]+self.pwm_data[i][0],
                                                                    y_pos+20,
                                                                    fill='yellow', outline='blue')
                self.balloon.tagbind(self.ard_canvas,
                                     self.pwm_bars[i],
                                     ('{} - {}\n'
                                      'Pin {}\n'
                                      'Freq: {}Hz\n'
                                      'Duty Cycle: {}%\n'
                                      'Phase Shift: {}'+u'\u00b0').format(
                                         min_from_sec(self.pwm_data[i][7]/1000),
                                         min_from_sec(self.pwm_data[i][8]/1000),
                                         self.pwm_data[i][3],
                                         self.pwm_data[i][4],
                                         self.pwm_data[i][5],
                                         self.pwm_data[i][6]))
        self.progress_shape = self.ard_canvas.create_rectangle(-1, 0,
                                                               1, self.ard_bckgrd_height,
                                                               fill='red')
        self.progress_text = self.ard_canvas.create_text(35, 0,
                                                         fill='white',
                                                         anchor=Tk.N)
        self.progbar = ProgressBar(self.ard_canvas,
                                   self.progress_shape,
                                   self.progress_text,
                                   self.ard_data.packet[3])
        self.prog_on.config(command=self.progbar_run)
        self.prog_off.config(state=Tk.DISABLED,
                             command=self.progbar_stop)

    def ard_decode_data(self, name, data_source):
        """
        Read packed up Arduino Data and puts it in proper format
        """
        time_seg = float(self.ard_data.packet[3])/1000
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
                                           trig_times[i][n+1]])
            final_intv = sorted(final_intv,
                                key=itemgetter(1))
            data_source = final_intv
        ard_data = []
        for i in data_source:
            start_space = (float(i[start])/time_seg)
            on_space = float(i[on])/time_seg-start_space
            if on_space == 0:
                start_space -= 1
                on_space = 1
            off_space = 1000-on_space-start_space
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

    # Progress Bar Functions
    def progbar_run(self):
        """
        Check if valid settings, make directories, and start progress bar
        """
        # Check folders are available
        if len(self.save_dir_list) == 0 and len(self.results_dir_used) == 0 and dirs.settings.save_dir == '':
            tkMb.showinfo('Error!',
                          'You must first create a directory to save data output.',
                          parent=self.master)
            return
        # Check devices are available
        #   first we setup Arduino...
        if self.ard_toggle_var.get() == 1:
            self.ard_ser = ArduinoComm(self.ard_queue)
        #   ... and LabJack
        if self.lj_toggle_var.get() == 1:
            if not self.lj_connected:
                try:
                    self.lj_device = LJU6()
                    self.lj_connected = True
                except (LabJackPython.LabJackException, LabJackPython.NullHandleException):
                    self.lj_status.set('** LabJack is not connected or '
                                       'is occupied by another program. '
                                       'Please reconnect the device.')
            self.lj_instance = LabJackComm(self.lj_queue, self.lj_device)
        # Thread Queues
        self.master_queue.queue.clear()
        self.ard_queue.queue.clear()
        self.lj_queue.queue.clear()
        # Disable non-essential buttons to avoid errors between modules
        self.run_bulk_toggle(running=True)
        # Start devices
        if self.ard_toggle_var.get() == 1:
            self.ard_ser.start()
        if self.lj_toggle_var.get() == 1:
            self.lj_instance.start()
        # Process the queues from device threads to see if we succeeded in connecting
        main_queue_success_msg = []
        main_queue_fail_msg = []
        if self.ard_toggle_var.get() == 1:
            self.gui_queue_process(success_msg=[self.ard_ser.success_msg],
                                   fail_msg=[self.ard_ser.fail_msg],
                                   queue=self.ard_queue, rate=10,
                                   header=self.ard_ser.msg_header,
                                   header_var=self.ard_status)
            main_queue_success_msg.append(self.ard_ser.success_msg)
            main_queue_fail_msg.append(self.ard_ser.fail_msg)
        if self.lj_toggle_var.get() == 1:
            self.gui_queue_process(success_msg=[self.lj_instance.success_msg],
                                   fail_msg=[self.lj_instance.fail_msg],
                                   queue=self.lj_queue, rate=10,
                                   header=self.lj_instance.msg_header,
                                   header_var=self.lj_status)
            main_queue_success_msg.append(self.lj_instance.success_msg)
            main_queue_fail_msg.append(self.lj_instance.fail_msg)
        # Main queue processing
        self.gui_queue_process(success_msg=main_queue_success_msg,
                               fail_msg=main_queue_fail_msg,
                               success_fn=self.run_experiment,
                               fail_fn=lambda: self.run_bulk_toggle(running=False),
                               queue=self.master_queue, rate=15)

    def progbar_stop(self):
        """
        Stops the progress bar
        """
        self.ard_queue.put('FailedArd')
        self.lj_queue.put('FailedLJ')
        self.progbar.stop()
        self.run_bulk_toggle(running=False)
        if self.ard_toggle_var.get() == 1:
            try:
                self.ard_ser.reset()
            except AttributeError:
                pass

    def run_experiment(self):
        """
        If we succeed in connecting to our devices, do this
        """
        # 1. Make sure there is somewhere to save our file outputs
        if len(self.results_dir_used) == 0:
            self.preresults_dir = str(dirs.main_save_dir)+dirs.settings.save_dir+'/'
            dirs.results_dir = self.preresults_dir+'{} at [{}]/'.format(get_day(2),
                                                                        get_day(3))
            self.make_save_dir = 1
            self.save_file_name.set('Currently Selected:\n[{}]'.format(
                limit_string_length(
                    dirs.settings.save_dir.upper(),
                    20)))
        if self.make_save_dir == 1 or not os.path.isdir(dirs.results_dir):
            os.makedirs(dirs.results_dir)
            self.results_dir_used[self.preresults_dir] = dirs.results_dir
            self.make_save_dir = 0
            self.save_grab_list()
        # 2. Pack up and send over data to the arduino
        system_time = ["<L", calendar.timegm(time.gmtime()) - TIME_OFFSET]
        pwm_pack_send = []
        for i in dirs.settings.ard_last_used['pwm_pack']:
            period = (float(1000000)/float(i[4]))
            cycleTimeOn = long(round(period*(float(i[7])/float(100))))
            cycleTimeOff = long(round(period*(float(1)-(float(i[7])/float(100)))))
            timePhaseShift = long(round(period*(float(i[6])/float(360))))
            pwm_pack_send.append(["<LLLLLBL",
                                  0, i[2], i[3],
                                  cycleTimeOn, cycleTimeOff,
                                  i[5], timePhaseShift])
        try:
            if self.ard_toggle_var.get() == 1:
                self.ard_status.set('Success! Connected to '
                                    'Port [{}]. '
                                    'Sending data '
                                    'packets...'.format(self.ard_ser.ser_port))
                self.ard_ser.send_packets([system_time],
                                          [dirs.settings.ard_last_used['packet']],
                                          dirs.settings.ard_last_used['tone_pack'],
                                          dirs.settings.ard_last_used['out_pack'],
                                          pwm_pack_send)
                self.ard_status.set('Success! Connected to '
                                    'Port [{}]. '
                                    'Data packets sent'.format(self.ard_ser.ser_port))
                self.ard_ser.send_to_ard(pack("<B", 1))
            # 3. Start the GUI Prog Bar
            running = self.progbar.start()
            if not running:
                if self.ard_toggle_var.get() == 1:
                    self.ard_ser.reset()
        except serial.serialutil.SerialException:
            self.ard_status.set('** Arduino was disconnected! '
                                'Reconnect the device and try again.')
        # Finished. Turn buttons back on
        self.run_bulk_toggle(running=False)

    # Experiment Run Functions
    def run_bulk_toggle(self, running):
        """
        Toggles all non-essential buttons to active
         or disabled based on running state
        """
        if running:
            self.master.protocol('WM_DELETE_WINDOW',
                                 lambda: self.hard_exit(allow=False))
            self.prog_off.config(state=Tk.NORMAL)
            self.prog_on.config(state=Tk.DISABLED)
            self.fp_checkbutton.config(state=Tk.DISABLED)
            self.start_gui_button.config(state=Tk.DISABLED)
            self.save_dir_menu.config(state=Tk.DISABLED)
            self.new_save_entry.config(state=Tk.DISABLED)
            self.new_save_button.config(state=Tk.DISABLED)
            self.lj_config_button.config(state=Tk.DISABLED)
            # self.debug_button.config(state=Tk.DISABLED)
            self.clr_svs_button.config(state=Tk.DISABLED)
            self.ard_preset_menu.config(state=Tk.DISABLED)
            self.min_entry.config(state=Tk.DISABLED)
            self.sec_entry.config(state=Tk.DISABLED)
            self.ard_time_confirm.config(state=Tk.DISABLED)
            self.tone_setup.config(state=Tk.DISABLED)
            self.out_setup.config(state=Tk.DISABLED)
            self.pwm_setup.config(state=Tk.DISABLED)
            self.ard_toggle_button.config(state=Tk.DISABLED)
            self.lj_toggle_button.config(state=Tk.DISABLED)
            self.cmr_toggle_button.config(state=Tk.DISABLED)
        if not running:
            self.master.protocol('WM_DELETE_WINDOW',
                                 self.hard_exit)
            self.prog_off.config(state=Tk.DISABLED)
            self.prog_on.config(state=Tk.NORMAL)
            self.fp_checkbutton.config(state=Tk.NORMAL)
            self.start_gui_button.config(state=Tk.NORMAL)
            self.save_dir_menu.config(state=Tk.NORMAL)
            self.new_save_entry.config(state=Tk.NORMAL)
            self.new_save_button.config(state=Tk.NORMAL)
            self.lj_config_button.config(state=Tk.NORMAL)
            # self.debug_button.config(state=Tk.NORMAL)
            self.clr_svs_button.config(state=Tk.NORMAL)
            self.ard_preset_menu.config(state=Tk.NORMAL)
            self.min_entry.config(state=Tk.NORMAL)
            self.sec_entry.config(state=Tk.NORMAL)
            self.ard_time_confirm.config(state=Tk.NORMAL)
            self.tone_setup.config(state=Tk.NORMAL)
            self.out_setup.config(state=Tk.NORMAL)
            self.pwm_setup.config(state=Tk.NORMAL)
            self.ard_toggle_button.config(state=Tk.NORMAL)
            self.lj_toggle_button.config(state=Tk.NORMAL)
            self.cmr_toggle_button.config(state=Tk.NORMAL)


class ScrollFrame(object):
    """
    Produces a scrollable canvas item
    """
    def __init__(self, master, num_args, rows, bottom_padding=0):
        self.rows = rows
        self.root = master
        self.num_args = num_args
        self.bottom_padding = bottom_padding
        # Top Frame
        self.top_frame = Tk.Frame(self.root)
        self.top_frame.grid(row=0, column=0,
                            columnspan=self.num_args,
                            sticky=Tk.N+Tk.S+Tk.E+Tk.W)
        # Scroll Bar
        v_bar = Tk.Scrollbar(self.root, orient=Tk.VERTICAL)
        self.canvas = Tk.Canvas(self.root, yscrollcommand=v_bar.set)
        v_bar['command'] = self.canvas.yview
        self.canvas.bind_all('<MouseWheel>', self.on_vertical)
        v_bar.grid(row=1, column=self.num_args, sticky=Tk.N+Tk.S)
        self.root.grid_columnconfigure(0, weight=1)
        self.root.grid_rowconfigure(0, weight=1)
        # Middle Frame
        self.middle_frame = Tk.Frame(self.canvas)
        # Bottom Frame
        self.bottom_frame = Tk.Frame(self.root)
        self.bottom_frame.grid(row=2, column=0, columnspan=self.num_args+1)

    def on_vertical(self, event):
        """
        :return:
         vertical position of scrollbar
        """
        self.canvas.yview_scroll(-1*event.delta, 'units')

    def finalize(self):
        """
        finishes scrollbar setup
        """
        self.canvas.create_window(0, 0, anchor=Tk.NW, window=self.middle_frame)
        self.canvas.grid(row=1, column=0,
                         columnspan=self.num_args, sticky=Tk.N+Tk.S+Tk.E+Tk.W)
        self.canvas.configure(scrollregion=(0, 0, 0, self.rows*28+self.bottom_padding))


class GUI(object):
    """
    Standard GUI Class for all GUIs to inherit from
    """
    def __init__(self, master):
        self.root = master
        # noinspection PyUnresolvedReferences
        self.root.title(self.title)
        self.root.resizable(width=False, height=False)
        self.ALL = Tk.N+Tk.E+Tk.S+Tk.W
        self.hard_stop = False
        self.root.protocol('WM_DELETE_WINDOW', self.hard_exit)
        self.root.wm_attributes("-topmost", 1)

    def hard_exit(self):
        """
        Destroy all instances of the window
        if close button is pressed
        Prevents ID errors and clashes
        """
        self.hard_stop = True
        self.root.destroy()
        self.root.quit()

    def center(self):
        """
        Centers GUI window
        :return:
            None
        """
        self.root.update_idletasks()
        screen_width = self.root.winfo_screenwidth()
        screen_height = self.root.winfo_screenheight()
        [window_width, window_height] = list(
            int(i) for i in
            self.root.geometry().split('+')[0].split('x'))
        x_pos = screen_width/2 - window_width/2
        y_pos = screen_height/2 - window_height/2
        self.root.geometry('{}x{}+{}+{}'.format(
            window_width,
            window_height,
            x_pos, y_pos))

    def run(self):
        """
        Initiate GUI
        :return:
            None
        """
        self.center()
        self.root.mainloop()

    @staticmethod
    def platform_geometry(windows, darwin):
        """
        Returns window dimensions based on platform
        """
        if sys.platform.startswith('win'):
            return windows
        elif sys.platform.startswith('darwin'):
            return darwin
        else:
            return False

    @staticmethod
    def create_tk_vars(types, num):
        """
        Turns input array into Tkinter Variables
        :param types: (Str) 'Int' or 'String'
        :param num: (Int) Number of Tk variables to return
        :return:
            List populated with Tkinter variables of the desired type
        """
        hold = []
        if types == 'Int':
            for i in range(num):
                hold.append(Tk.IntVar())
        elif types == 'String':
            for i in range(num):
                hold.append(Tk.StringVar())
        return hold


class PhotometryGUI(GUI):
    """
    GUI for Configuring Photometry Options
    *Does not affect actual program function
        - When saving file outputs, photometry config options
          are appended to aid in Lock-In Analysis
    Options appended: - Channels Used and associated Data column
                      - Sample stimulation frequencies (primary and isosbestic)
    """
    def __init__(self, master):
        self.title = 'Photometry Configuration'
        GUI.__init__(self, master)
        # Grab last used settings
        self.ch_num = dirs.settings.fp_last_used['ch_num']
        self.stim_freq = {'main': dirs.settings.fp_last_used['main_freq'],
                          'isos': dirs.settings.fp_last_used['isos_freq']}
        # Check Buttons
        self.chk_buttons = self.create_tk_vars('Int', 3)
        for i in range(len(self.chk_buttons)):
            self.chk_buttons[i].set(self.ch_num[i])
        Tk.Label(self.root,
                 text='\nPrevious Settings Loaded\n'
                 'These settings will be saved in your .csv outputs.\n',
                 relief=Tk.RAISED).pack(fill='both', expand='yes')
        data_frame = Tk.LabelFrame(self.root,
                                   text='Photometry Data Channel')
        true_frame = Tk.LabelFrame(self.root,
                                   text='Main Reference Channel')
        isos_frame = Tk.LabelFrame(self.root,
                                   text='Isosbestic Reference Channel')
        button_frames = [data_frame, true_frame, isos_frame]
        buttons = []
        for i in range(len(button_frames)):
            buttons.append(copy.deepcopy([[]]*NUM_LJ_CH))
        for frame_index in range(len(button_frames)):
            button_frames[frame_index].pack(fill='both', expand='yes')
            for i in range(NUM_LJ_CH):
                buttons[frame_index][i] = Tk.Radiobutton(
                    button_frames[frame_index],
                    text=str(i), value=i,
                    variable=self.chk_buttons[frame_index],
                    command=lambda (var, ind)=(self.chk_buttons[frame_index],
                                               frame_index):
                    self.select_button(var, ind))
                buttons[frame_index][i].pack(side=Tk.LEFT)
        # Entry Fields
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
        # Exit Button
        Tk.Button(self.root, text='FINISH', command=self.exit).pack(side=Tk.BOTTOM)

    def select_button(self, var, ind):
        """
        Changes button variables when user selects an option
        :param var: Button variable
        :param ind: Button index
        :return:
            None
        """
        if var.get() not in self.ch_num:
            self.ch_num[ind] = var.get()
        else:
            temp_report = ['Photometry Data Channel',
                           'Main Reference Channel',
                           'Isosbestic Reference Channel']
            temp_report = temp_report[self.ch_num.index(var.get())]
            tkMb.showinfo('Error!',
                          'You already selected \n['
                          'Channel {}] \n'
                          'for \n'
                          '[{}]!'.format(var.get(), temp_report),
                          parent=self.root)
            self.chk_buttons[ind].set(self.ch_num[ind])

    def exit(self):
        """
        Quit Photometry
        :return:
            None
        """
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
                self.root.destroy()
                dirs.settings.fp_last_used = {
                    'ch_num': self.ch_num,
                    'main_freq': self.stim_freq['main'],
                    'isos_freq': self.stim_freq['isos']}
                self.root.quit()
        except ValueError:
            tkMb.showinfo('Error!', 'Stimulation frequencies must be '
                                    'Integers in Hz.',
                          parent=self.root)


class LabJackGUI(GUI):
    """
    GUI for LabJack configuration
    """
    def __init__(self, master):
        self.lj_save_name = ''
        self.ch_num = dirs.settings.lj_last_used['ch_num']
        self.scan_freq = dirs.settings.lj_last_used['scan_freq']
        self.n_ch = len(self.ch_num)
        self.title = 'LabJack Configuration'
        GUI.__init__(self, master)
        ##############################
        # Load preset list
        self.preset_list = []
        self.update_preset_list()
        # Create frames
        left_frame = Tk.LabelFrame(self.root, text='Manual Configuration')
        left_frame.grid(row=0, column=0)
        right_frame = Tk.LabelFrame(self.root, text='Preset Configuration')
        right_frame.grid(row=0, column=1)
        # Load Presets
        Tk.Label(right_frame, text='\nChoose a Preset'
                                   '\nOr Save a '
                                   'New Preset:').pack(fill='both',
                                                       expand='yes')
        preset_frame = Tk.LabelFrame(right_frame, text='Select a Saved Preset')
        preset_frame.pack(fill='both', expand='yes')
        self.preset_chosen = Tk.StringVar()
        self.preset_chosen.set(max(self.preset_list, key=len))
        self.preset_menu = Tk.OptionMenu(preset_frame, self.preset_chosen,
                                         *self.preset_list,
                                         command=self.list_choose)
        self.preset_menu.pack(side=Tk.TOP)
        # Save New Presets
        new_preset_frame = Tk.LabelFrame(right_frame, text='(Optional): '
                                                           'Save New Preset')
        new_preset_frame.pack(fill='both', expand='yes')
        self.save_entry = Tk.Entry(new_preset_frame)
        self.save_entry.pack()
        Tk.Button(new_preset_frame, text='SAVE',
                  command=self.save_button).pack()
        ##############################
        # Manual Config
        Tk.Label(left_frame, text='\nMost Recently '
                                  'Used Settings:').pack(fill='both',
                                                         expand='yes')
        ch_frame = Tk.LabelFrame(left_frame, text='Channels Selected')
        ch_frame.pack(fill='both', expand='yes')
        # Create Check Buttons
        self.button_vars = self.create_tk_vars('Int', NUM_LJ_CH)
        buttons = copy.deepcopy([[]]*NUM_LJ_CH)
        for i in range(NUM_LJ_CH):
            buttons[i] = Tk.Checkbutton(ch_frame, text='{:0>2}'.format(i),
                                        variable=self.button_vars[i],
                                        onvalue=1, offvalue=0,
                                        command=self.select_button)
        for i in range(NUM_LJ_CH):
            buttons[i].grid(row=i//5, column=i-(i//5)*5)
        for i in self.ch_num:
            buttons[i].select()
        # Sampling Frequency Field
        scan_frame = Tk.LabelFrame(left_frame, text='Scan Frequency')
        scan_frame.pack(fill='both', expand='yes')
        Tk.Label(scan_frame, text='Freq/Channel (Hz):').pack(side=Tk.LEFT)
        self.scan_entry = Tk.Entry(scan_frame, width=8)
        self.scan_entry.pack(side=Tk.LEFT)
        self.scan_entry.insert(Tk.END, self.scan_freq)
        # Exit Button
        Tk.Button(self.root,
                  text='FINISH',
                  command=self.exit).grid(row=1, column=0, columnspan=2)

    def update_preset_list(self):
        """
        Updates self.preset_list with all available presets
        :return:
            None
        """
        self.preset_list = [i for i in dirs.settings.lj_presets]

    def select_button(self):
        """
        Inputs user selections on check buttons
        :return:
            None
        """
        redo = 0
        temp_ch_num = self.ch_num
        self.ch_num = []
        for i in range(NUM_LJ_CH):
            if self.button_vars[i].get() == 1:
                self.ch_num.append(i)
        self.n_ch = len(self.ch_num)
        if self.n_ch > 8:
            tkMb.showinfo('Error!',
                          'You cannot use more than 8 LabJack '
                          'Channels at once.',
                          parent=self.root)
            redo = 1
        elif self.n_ch == 0:
            tkMb.showinfo('Error!',
                          'You must configure at least one '
                          'Channel.',
                          parent=self.root)
            redo = 1
        if redo == 1:
            self.ch_num = temp_ch_num
            for i in range(NUM_LJ_CH):
                self.button_vars[i].set(0)
            for i in self.ch_num:
                self.button_vars[i].set(1)
            self.n_ch = len(self.ch_num)

    def save_button(self):
        """
        Saves and exits GUI
        :return:
            None
        """
        self.update_preset_list()
        validity = self.check_input_validity()
        if validity:
            save_name = self.save_entry.get().strip().lower()
            if len(save_name) == 0:
                tkMb.showinfo('Error!',
                              'You must give your Preset a name.',
                              parent=self.root)
            elif len(save_name) != 0:
                if save_name not in dirs.settings.lj_presets:
                    dirs.settings.lj_presets[save_name] = {
                        'ch_num': self.ch_num,
                        'scan_freq': self.scan_freq
                    }
                    tkMb.showinfo('Saved!', 'Preset saved as '
                                            '[{}]'.format(save_name),
                                  parent=self.root)
                    menu = self.preset_menu.children['menu']
                    menu.add_command(label=save_name,
                                     command=lambda name=save_name:
                                     self.list_choose(name))
                    self.preset_chosen.set(save_name)
                elif save_name in dirs.settings.lj_presets:
                    if tkMb.askyesno('Overwrite?',
                                     '[{}] already exists.\n'
                                     'Overwrite this preset?'.format(save_name),
                                     parent=self.root):
                        dirs.settings.lj_presets[save_name] = {
                            'ch_num': self.ch_num,
                            'scan_freq': self.scan_freq
                        }
                        tkMb.showinfo('Saved!', 'Preset saved as '
                                                '[{}]'.format(save_name),
                                      parent=self.root)

    def exit(self):
        """
        Close GUI
        :return:
            None
        """
        validity = self.check_input_validity()
        if validity:
            self.root.destroy()
            self.root.quit()

    def check_input_validity(self):
        """
        Checks if user inputs are valid
        :return:
            Validity (boolean)
        """
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
                self.scan_freq = int(self.scan_entry.get())
                max_freq = int(50000/self.n_ch)
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
                    dirs.settings.lj_last_used['ch_num'] = self.ch_num
                    dirs.settings.lj_last_used['scan_freq'] = self.scan_freq
            except ValueError:
                tkMb.showinfo('Error!', 'Scan Frequency must be an '
                                        'Integer in Hz.',
                              parent=self.root)
        return validity

    def list_choose(self, name):
        """
        Configures settings based on preset chosen
        :param name: name of preset picked
        :return:
            None
        """
        self.preset_chosen.set(name)
        self.ch_num = dirs.settings.lj_presets[name]['ch_num']
        self.scan_freq = dirs.settings.lj_presets[name]['scan_freq']
        for i in range(NUM_LJ_CH):
            self.button_vars[i].set(0)
        for i in self.ch_num:
            self.button_vars[i].set(1)
        self.n_ch = len(self.ch_num)
        self.scan_entry.delete(0, Tk.END)
        self.scan_entry.insert(Tk.END, self.scan_freq)


# noinspection PyAttributeOutsideInit,PyUnresolvedReferences,PyTypeChecker,PyStatementEffect,PyUnboundLocalVariable
class ArduinoGUI(GUI):
    """
    Handles user facing end of arduino communication
    then passes input information to ArduinoComm
    """
    def __init__(self, master):
        self.root = master
        self.close_gui = False
        self.title = 'n/a'
        GUI.__init__(self, master)
        self.num_entries = 0
        self.output_ids, self.pwm_ids = (range(2, 8), range(8, 14))
        self.pwm_ids.remove(10)
        # Pull last used settings
        [self.packet, self.tone_pack,
         self.out_pack, self.pwm_pack] = dirs.settings.quick_ard()
        self.max_time = 0
        self.data = {'starts': {}, 'middles': {}, 'ends': {}, 'hold': {}}
        self.types = None
        self.return_data = []
        self.fields_validated = {}

    def entry_validate(self, pins=False, rows=None):
        """
        Checks inputs are valid and exits
        """
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
            err_place_msg = 'row [{:0>2}]'.format(row+1)
        elif self.types == 'output':
            pin_ids = range(2, 8)
            pin_ids = pin_ids[pin]
            entry = self.entries[pin][row]
            arg_types = ['Time On (s)', 'Time until Off (s)']
            err_place_msg = 'row [{:0>2}], pin [{:0>2}]'.format(row+1, pin_ids)
        elif self.types == 'pwm':
            pin_ids = range(8, 14)
            pin_ids.remove(10)
            pin_ids = pin_ids[pin]
            entry = self.entries[pin][row]
            arg_types = ['Time On (s)', 'Time until Off (s)', 'Frequency (Hz)',
                         'Duty Cycle (%)', 'Phase Shift (deg)']
            err_place_msg = 'row [{:0>2}], pin [{:0>2}]'.format(row+1, pin_ids)
        ####################################################################
        # Grab comma separated user inputs as a list
        inputs = entry.get().split(',')
        for i in range(len(inputs)):
            inputs[i] = inputs[i].strip()
        # Now we begin to check entry validity
        # 1. Check Commas don't occur at ends or there exist any doubles:
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
            if i == 2:
                error_str += '\n'
            error_str += str(arg_types[i])
            if i < num_args-1:
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
        # 2b. Exactly 0
        if len(inputs) == 0:
            if close_gui:
                self.close()
            return False
        # 3. Check input content are valid
        try:
            on, off = int(inputs[0]), int(inputs[1])
            on_ms, off_ms = on*1000, off*1000
            refr, freq, phase, duty_cycle = [], 0, 0, 0
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
            # 3a. If on+off > main gui max time, we change gui time at close
            if (on_ms+off_ms) > self.max_time and off_ms != 0:
                    self.max_time = on_ms+off_ms
            # 3b. Time interval for each entry must be > 0
            if off_ms == 0:
                tkMb.showinfo('Error!',
                              'Error in {}:\n\n'
                              'Time Interval (i.e. '
                              'Time until On) '
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
        #
        # ...because pwm is a special butterfly and needs extra steps:
        if self.types == 'pwm':
            pin_int = pin_to_int(pin_ids)
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
        # e.g. due to edits
        # we will need to remove its previous set of data first.
        self.time_remove(rows, pins, refr)
        # 4b. test for time overlaps
        try:
            self.data['starts'][refr], self.data['middles'][refr], self.data['ends'][refr]
        except KeyError:
            self.data['starts'][refr], self.data['middles'][refr], self.data['ends'][refr] = [], [], []
        if self.types in ['tone', 'pwm']:
            try:
                self.data['hold'][refr]
            except KeyError:
                self.data['hold'][refr] = []
            (starts_all,
             middles_all,
             ends_all) = dict_flatten(self.data['starts'],
                                      self.data['middles'],
                                      self.data['ends'])
        elif self.types == 'output':
            (starts_all,
             middles_all,
             ends_all) = (self.data['starts'][pin_ids],
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
        self.data['middles'][refr] += range(on+1, on+off)
        front, back = 0, 0
        self.time_combine(on_ms, off_ms, front, back, refr)
        if on in self.data['ends'][refr] and on+off not in self.data['starts'][refr]:
            front, back = 1, 0
            self.data['middles'][refr].append(on)
            self.data['ends'][refr].remove(on)
            self.data['ends'][refr].append(on+off)
            self.time_combine(on_ms, off_ms, front, back, refr)
        elif on not in self.data['ends'][refr] and on+off in self.data['starts'][refr]:
            front, back = 0, 1
            self.data['middles'][refr].append(on+off)
            self.data['starts'][refr].remove(on+off)
            self.data['starts'][refr].append(on)
            self.time_combine(on_ms, off_ms, front, back, refr)
        elif on in self.data['ends'][refr] and on+off in self.data['starts'][refr]:
            front, back = 1, 1
            self.data['middles'][refr].append(on)
            self.data['middles'][refr].append(on+off)
            self.data['starts'][refr].remove(on+off)
            self.data['ends'][refr].remove(on)
            self.time_combine(on_ms, off_ms, front, back, refr)
        else:
            self.data['starts'][refr].append(on)
            self.data['ends'][refr].append(on+off)
        # Now we need to make sure this one comes out as an already validated field
        if self.types == 'tone':
            self.fields_validated[rows] = {'starts': on,
                                           'middles': range(on+1, on+off),
                                           'ends': on+off,
                                           'hold': [on_ms, on_ms+off_ms],
                                           'refr': refr}
        elif self.types == 'output':
            pin_int = pin_to_int(refr)
            self.fields_validated[rows+pins] = {'starts': on,
                                                'middles': range(on+1, on+off),
                                                'ends': on+off,
                                                'hold': {on_ms: pin_int, off_ms: pin_int},
                                                'refr': refr}
        elif self.types == 'pwm':
            self.fields_validated[rows+pins] = {'starts': on,
                                                'middles': range(on+1, on+off),
                                                'ends': on+off,
                                                'hold': [on_ms, on_ms+off_ms],
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

    def time_remove(self, rows, pins, refr):
        """
        Removes the indicated time segment
        """
        field = None
        field_refr = None
        if self.types == 'tone':
            try:
                self.fields_validated[rows]
            except KeyError:
                self.fields_validated[rows] = {'starts': -1, 'middles': [],
                                               'ends': -1, 'hold': [], 'refr': refr}
                return
            field = self.fields_validated[rows]
            field_refr = field['refr']
        elif self.types in ['output', 'pwm']:
            try:
                self.fields_validated[rows+pins]
            except KeyError:
                self.fields_validated[rows+pins] = {'starts': -1, 'middles': [],
                                                    'ends': -1, 'hold': [], 'refr': refr}
                return
            field = self.fields_validated[rows+pins]
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
                    self.data['hold'][field_refr].remove(field['starts']*1000)
                elif field['starts'] in self.data['middles'][field_refr]:
                    self.data['middles'][field_refr].remove(field['starts'])
                    self.data['ends'][field_refr].append(field['starts'])
                    self.data['hold'][field_refr].append(field['starts']*1000)
                if field['ends'] in self.data['ends'][field_refr]:
                    self.data['ends'][field_refr].remove(field['ends'])
                    self.data['hold'][field_refr].remove(field['ends']*1000)
                elif field['ends'] in self.data['middles'][field_refr]:
                    self.data['middles'][field_refr].remove(field['ends'])
                    self.data['starts'][field_refr].append(field['ends'])
                    self.data['hold'][field_refr].append(field['ends']*1000)
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
                self.data['hold'][field['starts']*1000], self.data['hold'][field['ends']*1000]
                # rm middles
                for i in field['middles']:
                    if i in self.data['middles'][field_refr]:
                        self.data['middles'][field_refr].remove(i)
                # rm s, e, h
                if field['starts'] in self.data['starts'][field_refr]:
                    self.data['starts'][field_refr].remove(field['starts'])
                    if self.data['hold'][field['starts']*1000] == pin_int:
                        self.data['hold'] = {key: self.data['hold'][key]
                                             for key in self.data['hold']
                                             if key != field['starts']*1000}
                    else:
                        self.data['hold'][field['starts']*1000] -= pin_int
                elif field['starts'] in self.data['middles'][field_refr]:
                    self.data['middles'][field_refr].remove(field['starts'])
                    self.data['ends'][field_refr].append(field['starts'])
                    if field['starts']*1000 in self.data['hold']:
                        self.data['hold'][field['starts']*1000] += pin_int
                    else:
                        self.data['hold'][field['starts']*1000] = pin_int
                if field['ends'] in self.data['ends'][field_refr]:
                    self.data['ends'][field_refr].remove(field['ends'])
                    if self.data['hold'][field['ends']*1000] == pin_int:
                        self.data['hold'] = {key: self.data['hold'][key]
                                             for key in self.data['hold']
                                             if key != field['ends']*1000}
                    else:
                        self.data['hold'][field['ends']*1000] -= pin_int
                elif field['ends'] in self.data['middles'][field_refr]:
                    self.data['middles'][field_refr].remove(field['ends'])
                    self.data['starts'][field_refr].append(field['ends'])
                    if field['ends']*1000 in self.data['hold']:
                        self.data['hold'][field['ends']*1000] += pin_int
                    else:
                        self.data['hold'][field['ends']*1000] = pin_int
                # set field to empty
                self.fields_validated[rows+pins] = {'starts': -1, 'middles': [],
                                                    'ends': -1, 'hold': [], 'refr': refr}
            except KeyError:
                pass

    def time_combine(self, on_ms, off_ms, front, back, refr):
        """
        Looks for combinable time intervals and joins
        them into a single instruction
        """
        if self.types in ['pwm', 'tone']:
            if front == 0 and back == 0:
                self.data['hold'][refr].append(on_ms)
                self.data['hold'][refr].append(on_ms+off_ms)
            if front == 1:
                self.data['hold'][refr].remove(on_ms)
                self.data['hold'][refr].remove(on_ms)
            if back == 1:
                self.data['hold'][refr].remove(on_ms+off_ms)
                self.data['hold'][refr].remove(on_ms + off_ms)
        elif self.types == 'output':
            pin_int = pin_to_int(refr)
            if front == 0 and back == 0:
                if on_ms not in self.data['hold']:
                    self.data['hold'][on_ms] = pin_int
                elif on_ms in self.data['hold']:
                    self.data['hold'][on_ms] += pin_int
                if on_ms+off_ms not in self.data['hold']:
                    self.data['hold'][on_ms+off_ms] = pin_int
                elif on_ms+off_ms in self.data['hold']:
                    self.data['hold'][on_ms+off_ms] += pin_int
            if front == 1:
                if self.data['hold'][on_ms] == (2*pin_int):
                    self.data['hold'].pop(on_ms)
                else:
                    self.data['hold'][on_ms] -= (2*pin_int)
            if back == 1:
                if self.data['hold'][on_ms+off_ms] == (2*pin_int):
                    self.data['hold'].pop(on_ms+off_ms)
                else:
                    self.data['hold'][on_ms+off] -= (2*pin_int)

    def close(self):
        """
        Exits GUI
        """
        # If we configured a max time higher than what it was before, update
        if self.max_time > dirs.settings.ard_last_used['packet'][3]:
            dirs.settings.ard_last_used['packet'][3] = self.max_time
            main.ttl_time = self.max_time
            main.grab_ard_data(destroy=True)
            mins = min_from_sec(self.max_time / 1000, option='min')
            secs = min_from_sec(self.max_time / 1000, option='sec')
            main.min_entry.delete(0, Tk.END)
            main.min_entry.insert(Tk.END, '{:0>2}'.format(mins))
            main.sec_entry.delete(0, Tk.END)
            main.sec_entry.insert(Tk.END, '{:0>2}'.format(secs))
        # Retrieve data that we saved up and load into MasterGUI
        self.return_data = []
        if self.types == 'output':
            self.return_data = self.data['hold']
        elif self.types == 'tone':
            for freq in self.data['hold']:
                self.data['hold'][freq] = sorted(self.data['hold'][freq])
                for i in range(len(self.data['hold'][freq])):
                    if i % 2 == 0:
                        self.return_data.append([self.data['hold'][freq][i],
                                                 self.data['hold'][freq][i+1],
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
                                                     self.data['hold'][pin_int][refr][i+1],
                                                     freq_i,
                                                     pin_int,
                                                     phase_i,
                                                     duty_i])
        self.root.destroy()
        self.root.quit()

    def button_toggle(self, tags):
        """
        Toggles the selected check button
        :param tags: tone, output, pwm
        :return:
            None
        """
        if tags == 'tone':
            if self.tone_var.get() == 0:
                for row in range(self.num_entries):
                    self.entries[row].configure(state=Tk.DISABLED)
            elif self.tone_var.get() == 1:
                for row in range(self.num_entries):
                    self.entries[row].configure(state=Tk.NORMAL)
        else:
            var, ind = None, None
            if tags in self.output_ids:
                ind = self.output_ids.index(tags)
                var = self.output_var[ind]
            elif tags in self.pwm_ids:
                ind = self.pwm_ids.index(tags)
                var = self.pwm_var[ind]
            if var.get() == 0:
                for entry in range(self.num_entries):
                    self.entries[ind][entry].configure(state=Tk.DISABLED)
            elif var.get() == 1:
                for entry in range(self.num_entries):
                    self.entries[ind][entry].configure(state=Tk.NORMAL)

    def pre_close(self):
        """
        Forces focus on button to do final validation check
        """
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
            self.close_gui = True
            self.closebutton.focus()
        else:
            self.close()

    def tone_setup(self):
        """
        Tone GUI for arduino
        :return:
            None
        """
        self.root.title('Tone Configuration')
        self.types = 'tone'
        num_pins, self.num_entries = 1, 15
        scroll_frame = ScrollFrame(self.root, num_pins, self.num_entries+1)
        # Setup Buttons
        self.tone_var = Tk.IntVar()
        self.tone_var.set(0)
        button = Tk.Checkbutton(scroll_frame.top_frame,
                                text='Enable Tone\n'
                                     '(Arduino Pin 10)',
                                variable=self.tone_var,
                                onvalue=1, offvalue=0,
                                command=lambda tags='tone': self.button_toggle(tags))
        button.pack()
        # Setup Entries
        self.entries = copy.deepcopy([[]]*self.num_entries)
        Tk.Label(scroll_frame.middle_frame,
                 text='Time On(s), '
                      'Time until Off(s), '
                      'Freq (Hz)').grid(row=0, column=1, sticky=self.ALL)
        for row in range(self.num_entries):
            Tk.Label(scroll_frame.middle_frame,
                     text='{:0>2}'.format(row+1)).grid(row=row+1, column=0)
            validate = (scroll_frame.middle_frame.register(self.entry_validate),
                        False, row)
            self.entries[row] = Tk.Entry(
                scroll_frame.middle_frame,
                validate='focusout',
                validatecommand=validate)
            self.entries[row].grid(row=row+1, column=1, sticky=self.ALL)
            self.entries[row].config(state=Tk.DISABLED)
        # Confirm button
        self.closebutton = Tk.Button(scroll_frame.bottom_frame,
                                     text='CONFIRM',
                                     command=self.pre_close)
        self.closebutton.pack(side=Tk.TOP)
        scroll_frame.finalize()
        # Finish setup
        self.center()
        geometry = self.platform_geometry('250x325', '257x272')
        if geometry:
            self.root.geometry(geometry)
        else:
            pass

    def output_setup(self):
        """
        Output GUI for Arduino
        :return:
            None
        """
        self.root.title('Simple Output Config.')
        self.types = 'output'
        num_pins, self.num_entries = 6, 15
        scroll_frame = ScrollFrame(self.root, num_pins, self.num_entries+1,
                                   bottom_padding=8)
        info_frame = Tk.LabelFrame(scroll_frame.top_frame,
                                   text='Enable Arduino Pins')
        info_frame.grid(row=0, column=0, sticky=self.ALL)
        Tk.Label(info_frame, text=' '*21).pack(side=Tk.RIGHT)
        Tk.Label(info_frame, text='Enable pins, then input instructions '
                                  'line by line with comma '
                                  'separation.',
                 relief=Tk.RAISED).pack(side=Tk.RIGHT)
        Tk.Label(info_frame, text=' '*21).pack(side=Tk.RIGHT)
        # Variables
        self.entries = []
        for pin in range(num_pins):
            self.entries.append([])
            for entry in range(self.num_entries):
                self.entries[pin].append([])
        button = copy.deepcopy([[]]*num_pins)
        self.output_var = self.create_tk_vars('Int', num_pins)
        # Setup items
        for pin in range(num_pins):
            button[pin] = Tk.Checkbutton(info_frame,
                                         text='PIN {:0>2}'.format(
                                             self.output_ids[pin]),
                                         variable=self.output_var[pin],
                                         onvalue=1, offvalue=0,
                                         command=lambda tags=self.output_ids[pin]:
                                         self.button_toggle(tags))
            button[pin].pack(side=Tk.LEFT)
            Tk.Label(scroll_frame.middle_frame,
                     text='Pin {:0>2}\n'
                          'Time On(s), '
                          'Time until Off(s)'.format(self.output_ids[pin])).grid(row=0,
                                                                                 column=1+pin)
            for row in range(self.num_entries):
                validate = (scroll_frame.middle_frame.register(self.entry_validate),
                            pin, row)
                Tk.Label(scroll_frame.middle_frame,
                         text='{:0>2}'.format(row+1)).grid(row=row+1, column=0)
                self.entries[pin][row] = Tk.Entry(scroll_frame.middle_frame, width=18,
                                                  validate='focusout',
                                                  validatecommand=validate)
                self.entries[pin][row].grid(row=row+1, column=1+pin)
                self.entries[pin][row].config(state=Tk.DISABLED)
        # Confirm Button
        self.closebutton = Tk.Button(scroll_frame.bottom_frame,
                                     text='CONFIRM',
                                     command=self.pre_close)
        self.closebutton.pack(side=Tk.TOP)
        # Finish GUI Setup
        scroll_frame.finalize()
        self.center()
        geometry = self.platform_geometry(windows='1000x400',
                                          darwin='1110x272')
        if geometry:
            self.root.geometry(geometry)
        else:
            pass

    def pwm_setup(self):
        """
        PWM Config GUI Setup
        """
        self.root.title('PWM Configuration')
        self.types = 'pwm'
        num_pins, self.num_entries = 5, 15
        scroll_frame = ScrollFrame(self.root, num_pins,
                                   self.num_entries+1, bottom_padding=24)
        info_frame = Tk.LabelFrame(scroll_frame.top_frame,
                                   text='Enable Arduino Pins')
        info_frame.grid(row=0, column=0, sticky=self.ALL)
        Tk.Label(info_frame, text=' '*2).pack(side=Tk.RIGHT)
        Tk.Label(info_frame, text='e.g. 0,180,200,20,90  (Per Field)',
                 relief=Tk.RAISED).pack(side=Tk.RIGHT)
        Tk.Label(info_frame, text=' '*2).pack(side=Tk.RIGHT)
        Tk.Label(info_frame,
                 text='Enable pins, then input instructions '
                      'with comma separation.',
                 relief=Tk.RAISED).pack(side=Tk.RIGHT)
        Tk.Label(info_frame,
                 text=' '*5).pack(side=Tk.RIGHT)
        # Variables
        self.entries = []
        for pin in range(num_pins):
            self.entries.append([])
            for entry in range(self.num_entries):
                self.entries[pin].append([])
        button = copy.deepcopy([[]]*num_pins)
        self.pwm_var = self.create_tk_vars('Int', num_pins)
        # Setup items
        for pin in range(num_pins):
            button[pin] = Tk.Checkbutton(
                info_frame,
                text='Pin {:0>2}'.format(self.pwm_ids[pin]),
                variable=self.pwm_var[pin],
                onvalue=1, offvalue=0,
                command=lambda tags=self.pwm_ids[pin]: self.button_toggle(tags))
            button[pin].pack(side=Tk.LEFT)
            Tk.Label(scroll_frame.middle_frame,
                     text='Pin {:0>2}\n'
                          'Time On(s), '
                          'Time until Off(s), \n'
                          'Freq (Hz), '
                          'Duty Cycle (%),\n'
                          'Phase Shift '.format(self.pwm_ids[pin])+'('+u'\u00b0'+')').grid(row=0, column=1+pin)
            for row in range(self.num_entries):
                validate = (scroll_frame.middle_frame.register(self.entry_validate),
                            pin, row)
                Tk.Label(scroll_frame.middle_frame,
                         text='{:0>2}'.format(row+1)).grid(row=row+1, column=0)
                self.entries[pin][row] = Tk.Entry(scroll_frame.middle_frame, width=25,
                                                  validate='focusout',
                                                  validatecommand=validate)
                self.entries[pin][row].grid(
                    row=row+1, column=1+pin)
                self.entries[pin][row].config(state='disabled')
        # Confirm Button
        self.closebutton = Tk.Button(scroll_frame.bottom_frame,
                                     text='CONFIRM',
                                     command=self.pre_close)
        self.closebutton.pack(side=Tk.TOP)
        # Finish Tone Setup
        scroll_frame.finalize()
        geometry = self.platform_geometry(windows=False,
                                          darwin='1100x280')
        if geometry:
            self.root.geometry(geometry)
        else:
            pass
        self.center()


#################################################################
# Threaded Tasks
# Tasks that run under the GUI and last more than 1s should
#   be threaded to prevent GUI freezing
###############################
# Progress Bar
class ProgressBar(threading.Thread):
    """
    Creates a dynamic progress bar
    """
    def __init__(self, canvas, bar, time_gfx, ms_total_time,):
        threading.Thread.__init__(self)
        self.daemon = True
        self.canvas = canvas
        self.segment_size = (float(ms_total_time/1000))/1000
        self.ms_total_time = ms_total_time
        self.bar = bar
        self.time_gfx = time_gfx
        self.running = False
        self.start_prog = None
        self.num_prog, self.num_time = 1, 1
        self.time_diff = 0

    def start(self):
        """
        Starts the progress bar
        """
        if self.num_prog != 1:
            self.canvas.move(self.bar, -self.num_prog+1, 0)
            if (-self.num_prog+1+35) < 0:
                text_move = max(-self.num_prog+1+35, -929)
                self.canvas.move(self.time_gfx, text_move, 0)
            self.num_prog, self.num_time = 1, 1
        self.start_prog = datetime.now()
        self.running = True
        while self.running:
            now = datetime.now()
            self.time_diff = (now - self.start_prog).seconds + float((now - self.start_prog).microseconds) / 1000000
            if self.time_diff / self.num_time >= 0.005:
                self.canvas.itemconfig(self.time_gfx,
                                       text='{}'.format(min_from_sec(self.time_diff, True)))
                self.num_time += 1
            if self.time_diff / self.num_prog >= self.segment_size:
                self.canvas.move(self.bar, 1, 0)
                if (self.num_prog > 35) and (self.num_prog < 965):
                    self.canvas.move(self.time_gfx, 1, 0)
                self.num_prog += 1
            self.canvas.update()
            time.sleep(0.005)
            if self.num_prog > 1000 or self.time_diff > float(self.ms_total_time / 1000):
                self.running = False
                return self.running

    def stop(self):
        """
        Stops the progress bar
        """
        self.running = False


# Arduino Communication
class ArduinoComm(threading.Thread):
    """
    Handles serial communication with arduino
    """
    def __init__(self, queue):
        threading.Thread.__init__(self)
        self.daemon = True
        self.baudrate = 115200
        self.ser_port = dirs.settings.ser_port
        # Markers are unicode chrs '<' and '>'
        self.start_marker, self.end_marker = 60, 62
        self.serial = None
        self.queue = queue
        self.success_msg = 'SuccessArd'
        self.fail_msg = 'FailedArd'
        self.msg_header = '<ardmsg>'

    def send_to_ard(self, send_str):
        """
        Sends packed str to arduino
        """
        self.serial.write(send_str)

    def get_from_ard(self):
        """
        Reads serial data from arduino
        """
        ard_string = ''
        byte_hold = 'z'
        byte_count = -1
        # We read and discard serial data until we hit '<'
        while ord(byte_hold) != self.start_marker:
            byte_hold = self.serial.read()
        # Then we read and record serial data until we hit '>'
        while ord(byte_hold) != self.end_marker:
            if ord(byte_hold) != self.start_marker:
                ard_string += byte_hold
                byte_count += 1
            byte_hold = self.serial.read()
        return ard_string

    def send_packets(self, *args):
        """
        Send experiment config to arduino
        """
        for each in args:
            for i in range(len(each)):
                if len(each) > 0:
                    try:
                        get_str = self.get_from_ard()
                        if get_str == 'M':
                            self.send_to_ard(pack(*each[i]))
                    except TypeError:
                        raise serial.serialutil.SerialException

    def run(self):
        """
        Tries every possible serial port
        """
        # We can't directly access the string variables
        # for arduino or labjack status messages as this
        # gets screwed up with threading.
        # so we queue up the messages as well with
        # a type specific header
        ports = list_serial_ports()
        self.queue.put('{}Connecting to Port '
                       '[{}]...'.format(self.msg_header, self.ser_port))
        connected = self.try_serial(self.ser_port)
        if connected:
            self.queue.put('{}Success! Connected to Port '
                           '[{}].'.format(self.msg_header, self.ser_port))
            self.queue.put(self.success_msg)
            return
        elif not connected:
            for port in ports:
                if self.try_serial(port):
                    self.ser_port = port
                    dirs.settings.ser_port = port
                    self.queue.put('{}** Failed to connect. '
                                   'Attempting next Port '
                                   '[{}]...'.format(self.msg_header, port))
                    self.queue.put(self.success_msg)
                    return
            self.queue.put('{}** Arduino cannot be reached! '
                           'Please make sure the device '
                           'is plugged in.'.format(self.msg_header))
            self.queue.put(self.fail_msg)
            return

    def wait_for(self):
        """
        Wait for ready message from arduino
        """
        msg = ''
        start = datetime.now()
        while msg.find('Arduino is ready') == -1:
            while self.serial.inWaiting() == 0:
                time.sleep(0.1)
                time_diff = get_time_diff(start)
                if time_diff > 3500:
                    return False
            msg = self.get_from_ard()
        if msg == 'Arduino is ready':
            return True

    def try_serial(self, port):
        """
        Given a port, attempts to connect to it
        """
        try:
            self.serial = serial.Serial(port, self.baudrate)
            try:
                success = self.wait_for()
                if success:
                    dirs.settings.ser_port = port
                    return True
                else:
                    return False
            except IOError:
                return False
        except (serial.SerialException, IOError):
            return False

    def reset(self):
        """
        Resets serial connection
        Useful for flushing
        """
        self.serial.setDTR(False)
        time.sleep(0.022)
        self.serial.setDTR(True)


##################
# LabJack
# Check LJ Connections
class LabJackComm(threading.Thread):
    """
    Checks if LJU6 is available or is being taken up by
    another program instance, disconnected, etc.
    """
    def __init__(self, queue, lj_device):
        threading.Thread.__init__(self)
        self.daemon = True
        self.queue = queue
        self.success_msg = 'SuccessLJ'
        self.fail_msg = 'FailedLJ'
        self.msg_header = '<ljmsg>'
        self.device = lj_device

    def run(self):
        """
        Attempts to connect to Labjack
        """
        self.queue.put('{}Connecting to LabJack...'.format(self.msg_header))
        try:
            self.device.open()
            self.device.close()
            self.queue.put('{}Connected to LabJack!'.format(self.msg_header))
            self.queue.put(self.success_msg)
            return
        except (LabJackPython.LabJackException, AttributeError):
            try:
                self.queue.put('{}** Failed to connect. '
                               'Attempting a '
                               'hard reset...'.format(self.msg_header))
                time.sleep(2)
                self.device.hardReset()
                time.sleep(2)
                self.device = LJU6()
                self.queue.put('{}Connected to LabJack!'.format(self.msg_header))
                self.queue.put(self.success_msg)
                return
            except (LabJackPython.LabJackException, AttributeError):
                self.queue.put('{}** LabJack cannot be reached! '
                               'Please reconnect the device.'.format(self.msg_header))
                self.queue.put(self.fail_msg)
                return


# Main LabJack class
# noinspection PyDefaultArgument
class LJU6(u6.U6):
    """
    Modified from stock U6 to include better
    Samples per packet / packet per request
    determination
    """
    def __init__(self, exp_lock, read_lock):
        u6.U6.__init__(self)
        self.data = Queue.Queue()
        # threading events to block other threads until ready
        self.exp_lock = exp_lock  # blocks progress bar, arduino, and camera
        self.read_lock = read_lock  # blocks data reading
        self.running = False
        self.ch_num = []
        self.scan_freq = 0
        self.n_ch = 0
        self.reinitialize_vars()
        self.time_start_read = 0

    @staticmethod
    def find_packets_per_req(scanFreq, nCh):
        """
        Returns optimal packets per request to use
        """
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
        """
        Returns optimal samples per packet to use
        """
        hold = []
        for i in range(scanFreq + 1):
            if i % nCh == 0:
                hold.append(i)
        return max(hold)

    def streamConfig(self, NumChannels=1, ResolutionIndex=0,
                     SamplesPerPacket=25, SettlingFactor=0,
                     InternalStreamClockFrequency=0, DivideClockBy256=False,
                     ScanInterval=1, ChannelNumbers=[0],
                     ChannelOptions=[0], ScanFrequency=None,
                     SampleFrequency=None):
        """
        Sets up LJ device
        """
        if NumChannels != len(ChannelNumbers) or NumChannels != len(ChannelOptions):
            raise LabJackPython.LabJackException("NumChannels must match length "
                                                 "of ChannelNumbers and ChannelOptions")
        if len(ChannelNumbers) != len(ChannelOptions):
            raise LabJackPython.LabJackException("len(ChannelNumbers) doesn't "
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
        if InternalStreamClockFrequency == 1:
            freq = float(48000000)
        else:
            freq = float(4000000)
        if DivideClockBy256:
            freq /= 256
        freq = freq/ScanInterval
        # Only happens for ScanFreq < 25, in which case
        # this number is generated as described above
        if SamplesPerPacket < 25:
            self.packetsPerRequest = 1
        elif SamplesPerPacket == 25:  # For all ScanFreq > 25.
            self.packetsPerRequest = self.find_packets_per_req(ScanFrequency, NumChannels)
        # Such that PacketsPerRequest*SamplesPerPacket % NumChannels == 0,
        # where min P/R is 1 and max 48 for nCh 1-6,8
        # and max 42 for nCh 7.
        self.samplesPerPacket = SamplesPerPacket

    def read_with_counter(self, num_requests, datacount_hold):
        """
        Given a number of requests, pulls from labjack
         and returns number of data pulled
        """
        reading = True
        datacount = 0
        while reading:
            return_dict = self.streamData(convert=False).next()
            self.data.put_nowait(copy.deepcopy(return_dict))
            datacount += 1
            if datacount >= num_requests:
                reading = False
        datacount_hold.append(datacount)

    def reinitialize_vars(self):
        """
        Reloads channel and frequency information in case they were changed
        call this before starting any lj streaming
        """
        self.ch_num = dirs.settings.lj_last_used['ch_num']
        self.scan_freq = dirs.settings.lj_last_used['scan_freq']
        self.n_ch = len(self.ch_num)

    # noinspection PyUnboundLocalVariable
    def read_stream_data(self):
        """
        Reads from stream and puts in queue
        """
        datacount_hold = []
        self.getCalibrationData()
        self.streamConfig(NumChannels=self.n_ch, ChannelNumbers=self.ch_num,
                          ChannelOptions=[0]*self.n_ch, ScanFrequency=self.scan_freq)
        ttl_time = dirs.settings.ard_last_used['packet'][3]
        max_requests = int(math.ceil(
            (float(self.scan_freq*self.n_ch*ttl_time/1000)/float(
                self.packetsPerRequest*self.samplesPerPacket))))
        small_request = int(round(
            (float(self.scan_freq*self.n_ch*0.5)/float(
                self.packetsPerRequest*self.samplesPerPacket))))
        self.open()
        self.streamStart()
        # We will read 3 segments: 0.5s before begin exp, during exp, and 0.5s after exp
        # 1. 0.5s before exp. start; extra collected for safety
        self.time_start_read = datetime.now()
        self.running = True
        self.read_lock.set()  # we will now allow data reading
        while self.running:
            self.read_with_counter(small_request, datacount_hold)
            # 2. read for duration of time specified in dirs.settings.ard_last_used['packet'][3]
            self.exp_lock.set()  # we also unblock progress bar, arduino, and camera threads
            time_start = datetime.now()
            self.read_with_counter(max_requests, datacount_hold)
            time_stop = datetime.now()
            # 3. read for another 0.5s after
            self.read_with_counter(small_request, datacount_hold)
            self.running = False
        time_stop_read = datetime.now()
        self.streamStop()
        self.close()
        self.data.queue.clear()
        # now we do some reporting
        # samples taken for each interval:
        multiplier = self.packetsPerRequest*self.streamSamplesPerPacket
        datacount_hold = (np.asarray(datacount_hold))*multiplier
        total_samples = sum(i for i in datacount_hold)
        # total run times for each interval
        before_run_time = get_time_diff(start_time=self.time_start_read, end_time=time_start, choice='us')
        run_time = get_time_diff(start_time=time_start, end_time=time_stop, choice='us')
        after_run_time = get_time_diff(start_time=time_stop, end_time=time_stop_read, choice='us')
        total_run_time = get_time_diff(start_time=self.time_start_read, end_time=time_stop_read, choice='us')
        # actual sampling frequencies
        overall_smpl_freq = int(round(float(total_samples)*1000)/total_run_time)
        overall_scan_freq = overall_smpl_freq/self.n_ch
        exp_smpl_freq = int(round(float(datacount_hold[1])*1000)/run_time)
        exp_scan_freq = exp_smpl_freq/self.n_ch

    def data_write_plot(self):
        """
        Reads from queue and writes to file/plots
        """
        missed_total, missed_list = 0, []
        save_file_name = '[name]-{}'.format(get_day(3))
        with open(dirs.results_dir+save_file_name+'.csv', 'w') as save_file:
            for i in range(self.n_ch):
                save_file.write('AIN{},'.format(self.ch_num[i]))
            save_file.write('\n')
            self.read_lock.wait() # wait for the go ahead from read_stream_data
            while self.running:
                try:
                    if not self.running:
                        break
                    result = self.data.get(timeout=1)
                    if result['errors'] != 0:
                        missed_total += result['missed']
                        missed_time = datetime.now()
                        time_diff = get_time_diff(start_time=self.time_start_read,
                                                  end_time=missed_time)
                        missed_list.append([copy.deepcopy(result['missed']),
                                            copy.deepcopy(float(time_diff)/1000)])
                    r = self.processStreamData(result['result'])
                    for each in range(len(r['AIN{}'.format(self.ch_num[0])])):
                        for i in range(self.n_ch):
                            save_file.write(str(r['AIN{}'.format(self.ch_num[i])][each])+',')
                        save_file.write('\n')
                except Queue.Empty:
                    print 'QUEUE IS EMPTY STOPPING (MOVE THIS LINE TO GUI)'
                    self.running = False
                    break



#################################################################
# Directories
class Directories(object):
    """
    File Formats:
    .frcl: Main Settings Pickle
    .csv: Standard comma separated file for data output
    """
    def __init__(self, root):
        self.root = root
        self.user_home = os.path.expanduser('~')
        self.main_save_dir = self.user_home+'/desktop/frCntrlSaves/'
        self.results_dir = ''
        self.settings = MainSettings()
        if not os.path.isfile(self.user_home+'/frSettings.frcl'):
            # Create Settings file if does not exist
            with open(self.user_home+'/frSettings.frcl', 'wb') as f:
                # Put in some example settings and presets
                self.settings.load_examples()
                pickle.dump(self.settings, f)
        if not os.path.exists(self.main_save_dir):
            os.makedirs(self.main_save_dir)

    def load(self):
        """
        Load last used settings
        """
        with open(self.user_home + '/frSettings.frcl', 'rb') as settings_file:
            self.settings = pickle.load(settings_file)
            self.settings.check_dirs()

    def save(self):
        """
        Save settings for future use.
        """
        with open(dirs.user_home + '/frSettings.frcl', 'wb') as settings_file:
            pickle.dump(self.settings, settings_file)

    def clear_saves(self, root_reference):
        """
        Removes all settings and save directories.
        """
        global SAVE_ON_EXIT
        if tkMb.askyesno('Warning!',
                         'This DELETES all settings, presets, '
                         'and data output saves!\n'
                         'It should be used for '
                         'debugging purposes only.\n\n'
                         'Are you sure?',
                         default='no',
                         parent=self.root):
            shutil.rmtree(self.user_home+'/desktop/frCntrlSaves/')
            os.remove(self.user_home+'/frSettings.frcl')
            time.sleep(0.5)
            tkMb.showinfo('Finished',
                          'All Settings and Save Directories Deleted.\n'
                          'Program will now exit.',
                          parent=self.root)
            SAVE_ON_EXIT = False
            root_reference.destroy()
            root_reference.quit()


#################################################################
# Main Settings
class MainSettings(object):
    """
    Only call this if and only if settings.frcl does not exist
    Otherwise we use pickle.load(settings.frcl) to create
    a MainSettings singleton.
    Object saves and holds all relevant parameters and presets
    """
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

    def load_examples(self):
        """
        Example settings
        """
        if sys.platform.startswith('win'):
            self.ser_port = 'COM1'
        else:
            self.ser_port = '/dev/tty.usbmodem1421'
        self.save_dir = ''
        self.fp_last_used = {'ch_num': [0, 1, 2],
                             'main_freq': 211,
                             'isos_freq': 531}
        self.lj_last_used = {'ch_num': [0, 1, 2],
                             'scan_freq': 6250}
        self.ard_last_used = {'packet': ['', 0, 0, 0, 0, 0, 0],
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
                             'pwm_pack': []},
                            'example 2':
                            {'packet': ['<BBLHHH', 255, 255, 300000, 3, 6, 2],
                             'tone_pack': [['<LLH', 30000, 60000, 2800],
                                           ['<LLH', 90000, 120000, 2800],
                                           ['<LLH', 240000, 270000, 2000]],
                             'out_pack': [['<LB', 58000, 140], ['<LB', 60000, 140],
                                          ['<LB', 115000, 128], ['<LB', 145000, 128],
                                          ['<LB', 200000, 32], ['<LB', 240000, 32]],
                             'pwm_pack': [['<LLLfBBf', 0, 0, 150000, 20, 1, 0, 50],
                                          ['<LLLfBBf', 0, 150000, 300000, 20, 1, 90, 20]]}}

    def check_dirs(self):
        """
        Creates a save directory named in our Last Used Dir. records
        if that directory does not exist
        :return:
            None
        """
        if self.save_dir != '':
            if not os.path.isdir(dirs.main_save_dir+self.save_dir):
                os.makedirs(dirs.main_save_dir+self.save_dir)

    def quick_ard(self):
        """
        Quickly returns all Arduino parameters
        :return:
            List
        """
        return [
            self.ard_last_used['packet'],
            self.ard_last_used['tone_pack'],
            self.ard_last_used['out_pack'],
            self.ard_last_used['pwm_pack']
        ]

    def quick_lj(self):
        """
        Quickly return all LabJack parameters
        :return:
            List
        """
        return [
            self.lj_last_used['ch_num'],
            self.lj_last_used['scan_freq']
        ]

    def quick_fp(self):
        """
        Quickly return all Photometry parameters
        :return:
            List
        """
        return [
            self.fp_last_used['ch_num'],
            self.fp_last_used['main_freq'],
            self.fp_last_used['isos_freq']
        ]


#################################################################
#################################################################
if __name__ == '__main__':

    # Open Tkinter instance
    tcl_root = Tk.Tk()

    # Setup all Directories
    dirs = Directories(tcl_root)

    # Load last used settings
    dirs.load()

    # Run Main Loop
    main = MasterGUI(tcl_root)
    main.master.mainloop()

    # Save Settings for Next Run
    if SAVE_ON_EXIT:
        dirs.save()
#################################################################
