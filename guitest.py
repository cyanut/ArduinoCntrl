import serial
import time
import os
import platform
import glob
import threading
import copy
import calendar
import traceback
import Queue
import pickle
import sys
from struct import *
from datetime import datetime
from operator import itemgetter
from pprint import pprint

import numpy as np
import Tkinter as Tk
import tkMessageBox as tkMb
import tkFont
import LabJackPython
import u6
from u6 import U6
import Pmw
# import flycapture2a as fc2


#################################################################
# Global Constants
NUM_LJ_CH = 14


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
        self.grab_save_list()
        # Primary Save Frame
        save_frame = Tk.LabelFrame(self.master,
                                   text='Data Output Save Location',
                                   width=self.single_widget_dim*2,
                                   height=self.single_widget_dim,
                                   highlightthickness=5)
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
        Tk.Button(new_frame,
                  text='Create New',
                  command=lambda:
                  self.save_button_options(new=True)).pack(side=Tk.TOP)
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
        self.lj_config_button.pack(side=Tk.LEFT, expand=True)
        self.lj_test_button = Tk.Button(lj_frame,
                                        text='Test LabJack',
                                        command=self.lj_test)
        self.lj_test_button.pack(side=Tk.RIGHT, expand=True)
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
                      'Rollover individual segments for '
                      'specific stimuli config information.',
                 relief=Tk.RAISED).grid(row=0,
                                        columnspan=80,
                                        sticky=self.ALL)
        # Debug Button (Prints all attributes of dirs.settings)
        Tk.Button(ard_frame,
                  text='DEBUG',
                  command=lambda: pprint(vars(dirs.settings))).grid(row=0,
                                                                    column=80,
                                                                    columnspan=20,
                                                                    sticky=self.ALL)
        # Main Progress Canvas
        self.ard_canvas = Tk.Canvas(ard_frame,
                                    width=1050,
                                    height=self.ard_bckgrd_height+10)
        self.ard_canvas.grid(row=1,
                             column=0,
                             columnspan=100)
        self.canvas_init()
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
        self.grab_ard_data()
        # Arduino Presets
        as_row = 7
        self.update_ard_preset_list()
        self.ard_preset_chosen = Tk.StringVar()
        self.ard_preset_chosen.set('{: <40}'.format('(select a preset)'))
        self.ard_preset_menu = Tk.OptionMenu(ard_frame,
                                             self.ard_preset_chosen,
                                             *self.ard_preset_list,
                                             command=lambda file_in:
                                             self.grab_ard_data(True, file_in))
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
        Tk.Button(ard_frame, text='Confirm', command=self.get_ttl_time).grid(row=ts_row+1, column=4, sticky=Tk.W)
        # Tone Config
        Tk.Button(ard_frame,
                  text='Tone Setup',
                  command=lambda types='tone':
                  self.ard_config(types)).grid(row=5, column=0, sticky=self.ALL)
        Tk.Button(ard_frame,
                  text='PWM Setup',
                  command=lambda types='pwm':
                  self.ard_config(types)).grid(row=5, column=1, columnspan=3,
                                               sticky=self.ALL)
        Tk.Button(ard_frame,
                  text='Simple Outputs',
                  command=lambda types='output':
                  self.ard_config(types)).grid(row=6, column=0, sticky=self.ALL)
        # Update Window
        self.update_window()

    def get_ttl_time(self):
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
            self.grab_ard_data(destroy=True)
        except ValueError:
            tkMb.showinfo('Error!',
                          'Time must be entered as integers',
                          parent=self.master)

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

    def update_ard_preset_list(self):
        """
        List of all Arduino Presets
        """
        self.ard_preset_list = [i for i in dirs.settings.ard_presets]

    def canvas_init(self):
        """
        Setup Progress bar Canvas
        """
        # Backdrop
        self.ard_canvas.create_rectangle(0, 0,
                                         1050, self.ard_bckgrd_height,
                                         fill='black', outline='black')
        self.ard_canvas.create_rectangle(0, 35-1,
                                         1050, 35+1,
                                         fill='white')
        self.ard_canvas.create_rectangle(0, 155-1,
                                         1050, 155+1,
                                         fill='white')
        self.ard_canvas.create_rectangle(0, 15-1,
                                         1050, 15+1,
                                         fill='white')
        self.ard_canvas.create_rectangle(0, self.ard_bckgrd_height-5-1,
                                         1050, self.ard_bckgrd_height-5+1,
                                         fill='white')
        self.ard_canvas.create_rectangle(0, 15,
                                         0, self.ard_bckgrd_height-5,
                                         fill='white', outline='white')
        self.ard_canvas.create_rectangle(1000, 15,
                                         1013, self.ard_bckgrd_height-5,
                                         fill='white', outline='white')
        # Type Labels
        self.ard_canvas.create_rectangle(1000, 0,
                                         1013, 15,
                                         fill='black')
        self.ard_canvas.create_text(1000+7, 15+10,
                                    text=u'\u266b', fill='black')
        self.ard_canvas.create_rectangle(1000, 35,
                                         1013, 35,
                                         fill='black')
        self.ard_canvas.create_text(1000+7, 35+10,
                                    text='S', fill='black')
        self.ard_canvas.create_text(1000+7, 55+10,
                                    text='I', fill='black')
        self.ard_canvas.create_text(1000+7, 75+10,
                                    text='M', fill='black')
        self.ard_canvas.create_text(1000+7, 95+10,
                                    text='P', fill='black')
        self.ard_canvas.create_text(1000+7, 115+10,
                                    text='L', fill='black')
        self.ard_canvas.create_text(1000+7, 135+10,
                                    text='E', fill='black')
        self.ard_canvas.create_rectangle(1000, 155,
                                         1013, 155,
                                         fill='black')
        self.ard_canvas.create_text(1000+7, 175+10,
                                    text='P', fill='black')
        self.ard_canvas.create_text(1000+7, 195+10,
                                    text='W', fill='black')
        self.ard_canvas.create_text(1000+7, 215+10,
                                    text='M', fill='black')
        self.ard_canvas.create_rectangle(1000, self.ard_bckgrd_height-5,
                                         1013, self.ard_bckgrd_height,
                                         fill='black')
        # Arduino Pin Labels
        self.ard_canvas.create_text(1027+6, 9,
                                    text='PINS', fill='white')
        self.ard_canvas.create_text(1027+6, 15+10,
                                    text='10', fill='white')
        self.ard_canvas.create_text(1027+6, 35+10,
                                    text='02', fill='white')
        self.ard_canvas.create_text(1027+6, 55+10,
                                    text='03', fill='white')
        self.ard_canvas.create_text(1027+6, 75+10,
                                    text='04', fill='white')
        self.ard_canvas.create_text(1027+6, 95+10,
                                    text='05', fill='white')
        self.ard_canvas.create_text(1027+6, 115+10,
                                    text='06', fill='white')
        self.ard_canvas.create_text(1027+6, 135+10,
                                    text='07', fill='white')
        self.ard_canvas.create_text(1027+6, 155+10,
                                    text='08', fill='white')
        self.ard_canvas.create_text(1027+6, 175+10,
                                    text='09', fill='white')
        self.ard_canvas.create_text(1027+6, 195+10,
                                    text='11', fill='white')
        self.ard_canvas.create_text(1027+6, 215+10,
                                    text='12', fill='white')
        self.ard_canvas.create_text(1027+6, 235+10,
                                    text='13', fill='white')

    def grab_ard_data(self, destroy=False, load=False):
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
            self.tone_data = self.decode_ard_data('tone', self.ard_data.tone_pack)
            self.tone_bars = [[]]*len(self.tone_data)
            for i in range(len(self.tone_data)):
                self.tone_bars[i] = self.ard_canvas.create_rectangle(self.tone_data[i][0],
                                                                     0+15,
                                                                     self.tone_data[i][1]+self.tone_data[i][0],
                                                                     35, fill='yellow',
                                                                     outline='white')
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
            self.out_data = self.decode_ard_data('output',
                                                 self.ard_data.out_pack)
            self.out_bars = [[]]*len(self.out_data)
            for i in range(len(self.out_data)):
                y_pos = 35+(pin_ids.index(self.out_data[i][3]))*20
                self.out_bars[i] = self.ard_canvas.create_rectangle(self.out_data[i][0],
                                                                    y_pos,
                                                                    self.out_data[i][1]+self.out_data[i][0],
                                                                    y_pos+20,
                                                                    fill='yellow',
                                                                    outline='white')
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
            self.pwm_data = self.decode_ard_data('pwm', self.ard_data.pwm_pack)
            self.pwm_bars = [[]]*len(self.pwm_data)
            for i in range(len(self.pwm_data)):
                y_pos = 155+(pin_ids.index(self.pwm_data[i][3]))*20
                self.pwm_bars[i] = self.ard_canvas.create_rectangle(self.pwm_data[i][0],
                                                                    y_pos,
                                                                    self.pwm_data[i][1]+self.pwm_data[i][0],
                                                                    y_pos+20,
                                                                    fill='yellow', outline='white')
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
                                   self.prog_on,
                                   self.prog_off,
                                   self.ard_data.packet[3])
        self.prog_on.config(command=self.progbar_run)
        self.prog_off.config(state=Tk.DISABLED,
                             command=self.progbar.stop)

    def decode_ard_data(self, name, data_source):
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

    def update_window(self):
        """
        Update GUI Idle tasks, and centers
        """
        self.master.update_idletasks()
        screen_width = self.master.winfo_screenwidth()
        screen_height = self.master.winfo_screenheight()
        [window_width, window_height] = list(int(i) for i in
                                             self.master.geometry().split('+')[0].split('x'))
        x_pos = screen_width/2 - window_width/2
        y_pos = screen_height/2 - window_height/2
        self.master.geometry('{}x{}+{}+{}'.format(window_width,
                                                  window_height,
                                                  x_pos, y_pos))

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

    def grab_save_list(self):
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
        self.grab_save_list()
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

    def progbar_run(self):
        """
        Check if valid settings, make directories, and start progress bar
        """
        if len(self.save_dir_list) == 0 and len(self.results_dir_used) == 0 and dirs.settings.save_dir == '':
            tkMb.showinfo('Error!',
                          'You must first create a directory to save data output.',
                          parent=self.master)
        else:
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
                self.grab_save_list()
            self.progbar.start()

    def lj_config(self):
        """
        Opens LJ GUI for settings config
        """
        config = Tk.Toplevel(self.master)
        config_run = LabJackGUI(config)
        config_run.run()
        channels, freq = dirs.settings.quick_lj()
        self.lj_str_var.set('Channels:\n{}\n'
                            '\nScan Freq: [{}Hz]'.format(channels,
                                                         freq))

    def lj_test(self):
        """
        Checks if LabJack can be successfully connected
        """
        while True:
            try:
                temp = u6.U6()
                temp.close()
                time.sleep(0.5)
                temp = u6.U6()
                temp.hardReset()
                tkMb.showinfo('Success!',
                              'The LabJack has been properly configured',
                              parent=self.master)
                break
            except LabJackPython.NullHandleException:
                try:
                    temp = u6.U6()
                    temp.hardReset()
                except LabJackPython.NullHandleException:
                    retry = tkMb.askretrycancel('Error!',
                                                'The LabJack is either unplugged '
                                                'or is malfunctioning.\n\n'
                                                'Disconnect and reconnect the device, '
                                                'then click Retry.',
                                                parent=self.master)
                    if retry:
                        time.sleep(3)
                    else:
                        break
            time.sleep(0.001)


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
                print 1
                tkMb.showinfo('Error!', 'Stimulation Frequencies '
                                        'must be higher than 0 Hz!',
                              parent=self.root)
            elif true_freq == isos_freq:
                print 2
                tkMb.showinfo('Error!', 'Main sample and Isosbestic Frequencies '
                                        'should not be the same value.',
                              parent=self.root)
            else:
                print 3
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
        self.max_req, self.small_req = 0, 0
        self.stl_fctr, self.res_indx = 1, 0
        self.lj_save_name = ''
        self.ch_num = dirs.settings.lj_last_used['ch_num']
        self.scan_freq = dirs.settings.lj_last_used['scan_freq']
        self.n_ch, self.ch_opt = len(self.ch_num), [0]*len(self.ch_num)
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
        self.n_ch, self.ch_opt = len(self.ch_num), [0]*len(self.ch_num)
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
            self.n_ch, self.ch_opt = len(self.ch_num), [0]*len(self.ch_num)

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
        self.n_ch, self.ch_opt = len(self.ch_num), [0]*len(self.ch_num)
        self.scan_entry.delete(0, Tk.END)
        self.scan_entry.insert(Tk.END, self.scan_freq)


# noinspection PyAttributeOutsideInit
class ArduinoGUI(GUI):
    """
    Arduino GUI Configuration
    """
    def __init__(self, master):
        self.root = master
        self.title = 'n/a'
        GUI.__init__(self, master)
        self.baudrate = 115200
        self.num_entries = 0
        self.output_ids, self.pwm_ids = (range(2, 8), range(8, 14))
        self.pwm_ids.remove(10)
        # Pull last used settings
        self.ser_port = dirs.settings.ser_port
        [self.packet, self.tone_pack,
         self.out_pack, self.pwm_pack] = dirs.settings.quick_ard()

    def confirm(self, types):
        """
        Checks inputs are valid and exits
        """
        validity = False
        if types == 'tone':
            pass
        elif types == 'pwm':
            pass
        elif types == 'output':
            pass
        validity = True
        if validity:
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
                for entry in range(self.columns):
                    for row in range(self.num_entries):
                        self.entries[row][entry].configure(state=Tk.DISABLED)
            elif self.tone_var.get() == 1:
                for entry in range(self.columns):
                    for row in range(self.num_entries):
                        self.entries[row][entry].configure(state=Tk.NORMAL)
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

    def tone_setup(self):
        """
        Tone GUI for arduino
        :return:
            None
        """
        self.root.title('Tone Configuration')
        num_pins, self.num_entries, self.columns = 1, 15, 3
        scroll_frame = ScrollFrame(self.root, num_pins, self.num_entries+1)
        # Setup Buttons
        self.tone_var = Tk.IntVar()
        self.tone_var.set(0)
        button = Tk.Checkbutton(scroll_frame.top_frame,
                                text='Enable Tone (Arduino Pin 10)',
                                variable=self.tone_var,
                                onvalue=1, offvalue=0,
                                command=lambda tags='tone': self.button_toggle(tags))
        button.pack()
        # Setup Entries
        self.entries = []
        for i in range(self.num_entries):
            self.entries.append(copy.deepcopy([copy.deepcopy([])]*self.columns))
        Tk.Label(scroll_frame.middle_frame, text='Time On(s)').grid(row=0, column=1)
        Tk.Label(scroll_frame.middle_frame, text='Time Off(s)').grid(row=0, column=2)
        Tk.Label(scroll_frame.middle_frame, text='Freq(Hz)').grid(row=0, column=3)
        for row in range(self.num_entries):
            Tk.Label(scroll_frame.middle_frame,
                     text='{:0>2}'.format(row+1)).grid(row=row+1, column=0)
            for entry in range(3):
                self.entries[row][entry] = Tk.Entry(
                    scroll_frame.middle_frame, width=7)
                self.entries[row][entry].grid(
                    row=row+1, column=entry+1)
                self.entries[row][entry].config(state=Tk.DISABLED)
        # Confirm button
        Tk.Button(scroll_frame.bottom_frame,
                  text='CONFIRM',
                  command=lambda:
                  self.confirm('tone')).pack(side=Tk.TOP)
        scroll_frame.finalize()
        # Finish setup
        self.center()
        self.root.geometry('257x272')

    def output_setup(self):
        """
        Output GUI for Arduino
        :return:
            None
        """
        self.root.title('Simple Output Config.')
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
                          'Time Off(s)'.format(self.output_ids[pin])).grid(row=0,
                                                                           column=1+pin)
            for row in range(self.num_entries):
                Tk.Label(scroll_frame.middle_frame,
                         text='{:0>2}'.format(row+1)).grid(row=row+1, column=0)
                self.entries[pin][row] = Tk.Entry(scroll_frame.middle_frame, width=18)
                self.entries[pin][row].grid(row=row+1, column=1+pin)
                self.entries[pin][row].config(state=Tk.DISABLED)
        # Confirm Button
        Tk.Button(scroll_frame.bottom_frame,
                  text='CONFIRM',
                  command=lambda:
                  self.confirm('output')).pack(side=Tk.TOP)
        # Finish GUI Setup
        scroll_frame.finalize()
        self.root.geometry('980x280')
        self.center()

    def pwm_setup(self):
        """
        PWM Config GUI Setup
        :return:
        """
        self.root.title('PWM Configuration')
        num_pins, self.num_entries = 5, 15
        scroll_frame = ScrollFrame(self.root, num_pins,
                                   self.num_entries+1, bottom_padding=24)
        info_frame = Tk.LabelFrame(scroll_frame.top_frame,
                                   text='Enable Arduino Pins')
        info_frame.grid(row=0, column=0, sticky=self.ALL)
        Tk.Label(info_frame, text=' '*6).pack(side=Tk.RIGHT)
        Tk.Label(info_frame, text='e.g. 0,180,200,20,90   (Per Entry Box)',
                 relief=Tk.RAISED).pack(side=Tk.RIGHT)
        Tk.Label(info_frame, text=' '*5).pack(side=Tk.RIGHT)
        Tk.Label(info_frame,
                 text='Enable pins, then input instructions '
                      'line by line with comma separation.',
                 relief=Tk.RAISED).pack(side=Tk.RIGHT)
        Tk.Label(info_frame,
                 text=' '*10).pack(side=Tk.RIGHT)
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
                          'On(s), '
                          'Off(s), '
                          'Freq(Hz),\n'
                          'Duty Cycle (%), '
                          'Phase Shift (Deg)'.format(self.pwm_ids[pin])).grid(row=0,
                                                                              column=1+pin)
            for row in range(self.num_entries):
                Tk.Label(scroll_frame.middle_frame,
                         text='{:0>2}'.format(row+1)).grid(row=row+1, column=0)
                self.entries[pin][row] = Tk.Entry(
                    scroll_frame.middle_frame, width=25)
                self.entries[pin][row].grid(
                    row=row+1, column=1+pin)
                self.entries[pin][row].config(state='disabled')
        # Confirm Button
        Tk.Button(scroll_frame.bottom_frame,
                  text='CONFIRM',
                  command=lambda:
                  self.confirm('pwm')).pack(side=Tk.TOP)
        # Finish Tone Setup
        scroll_frame.finalize()
        self.root.geometry('1100x280')
        self.center()


class ProgressBar(threading.Thread):
    """
    Creates a dynamic progress bar
    """
    def __init__(self, canvas, bar, time_gfx, button_on, button_off, ms_total_time):
        threading.Thread.__init__(self)
        self.canvas = canvas
        self.segment_size = (float(ms_total_time/1000))/1000
        self.ms_total_time = ms_total_time
        self.bar = bar
        self.time_gfx = time_gfx
        self.running = False
        self.start_prog = None
        self.num_prog, self.num_time = 1, 1
        self.button_on = button_on
        self.button_off = button_off
        self.time_diff = 0

    def advance(self):
        """
        Moves the progress bar
        """
        while self.running:
            now = datetime.now()
            self.time_diff = (now-self.start_prog).seconds+float((now-self.start_prog).microseconds)/1000000
            if self.time_diff/self.num_time >= 0.005:
                self.canvas.itemconfig(self.time_gfx,
                                       text='{}'.format(min_from_sec(self.time_diff, True)))
                self.num_time += 1
            if self.time_diff/self.num_prog >= self.segment_size:
                self.canvas.move(self.bar, 1, 0)
                if (self.num_prog > 35) and (self.num_prog < 965):
                    self.canvas.move(self.time_gfx, 1, 0)
                self.num_prog += 1
            self.canvas.update()
            time.sleep(0.005)
            if self.num_prog > 1000 or self.time_diff > float(self.ms_total_time/1000):
                self.running = False
                self.button_on.config(state=Tk.DISABLED)
                self.button_off.config(state=Tk.NORMAL)

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
        self.button_on.config(state=Tk.DISABLED)
        self.button_off.config(state=Tk.NORMAL)
        self.advance()

    def stop(self):
        """
        Stops the progress bar
        """
        self.button_on.config(state=Tk.NORMAL)
        self.button_off.config(state=Tk.DISABLED)
        self.running = False


#################################################################
# Directories
class Directories(object):
    """
    File Formats:
    .frcl: Main Settings Pickle
    .csv: Standard comma separated file for data output
    """
    def __init__(self):
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
        self.lj_last_used = {'ch_num': [], 'scan_freq': 0}
        self.ard_last_used = {
            'packet': [],
            'tone_pack': [],
            'out_pack': [],
            'pwm_pack': []}
        self.lj_presets = {}
        self.ard_presets = {}

    def load_examples(self):
        """
        Example Presets
        """
        if sys.platform.startswith('win'):
            self.ser_port = 'COM1'
        else:
            self.ser_port = '/dev/tty.usbmodem1421'
        self.save_dir = ''
        self.fp_last_used = {'ch_num': [0, 1, 2],
                             'main_freq': 211,
                             'isos_freq': 531}
        self.lj_last_used = {'ch_num': [], 'scan_freq': 0}
        self.ard_last_used = {
            'packet': ['<BBLHHH', 255, 255, 0, 0, 0, 0],
            'tone_pack': [],
            'out_pack': [],
            'pwm_pack': []
        }
        # All Saved Presets
        self.lj_presets = {'example': {'ch_num': [0, 1, 2, 10, 11],
                                       'scan_freq': 6250}}
        self.ard_presets = {'example':
                            {'packet': ['<BBLHHH', 255, 255,
                                        180000, 1, 2, 0],
                                'tone_pack': [['<LLH', 120000, 150000, 2800]],
                                'out_pack': [['<LB', 148000, 4],
                                             ['<LB', 150000, 4]],
                                'pwm_pack': []}
                            }

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
# Main Program
# Setup all Directories and load Last Used Settings
dirs = Directories()
dirs.load()

# Run Main Loop
main = MasterGUI(Tk.Tk())
main.master.mainloop()

# Save Settings for Next Run
dirs.save()
#################################################################
