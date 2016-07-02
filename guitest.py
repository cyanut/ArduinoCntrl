import Tkinter as tk
import tkMessageBox as tkmb
import serial, time, ast, os, sys, platform, glob, threading, thread, copy, Pmw
import calendar, traceback, re, LabJackPython, math, Queue, struct, u6, tkFont
from struct import *
from u6 import U6
from operator import itemgetter
from datetime import datetime
import numpy as np
#import flycapture2a as fc2

#####
#GUIs
class ScrollFrame():
    def __init__(self,master,numArgs,rows,bottompadding=0):
        self.rows = rows
        self.root = master
        self.numArgs = numArgs
        self.bottompadding = bottompadding
        ##topframe
        self.topFrame = tk.Frame(self.root)
        self.topFrame.grid(row=0,column=0,columnspan=numArgs,
            sticky=tk.E+tk.N+tk.W+tk.S)
        ##scrollbar
        vsb = tk.Scrollbar(self.root,orient=tk.VERTICAL)
        self.canvas = tk.Canvas(self.root,yscrollcommand=vsb.set)
        vsb['command'] = self.canvas.yview
        self.canvas.bind_all("<MouseWheel>", self.on_vertical)
        vsb.grid(row=1,column=numArgs,sticky=(tk.N,tk.S))
        self.root.grid_columnconfigure(0,weight=1)
        self.root.grid_rowconfigure(0,weight=1)
        ##middleframe
        self.middleFrame = tk.Frame(self.canvas)
        ##bottomframe
        self.bottomFrame = tk.Frame(self.root)
        self.bottomFrame.grid(row=2,column=0,columnspan=numArgs+1)
    def on_vertical(self,event):
        self.canvas.yview_scroll(-1 * event.delta, 'units')
    def finalize(self):
        self.canvas.create_window(0,0,anchor=tk.NW,window=self.middleFrame)
        self.canvas.grid(row=1, column=0, 
            columnspan=self.numArgs,sticky=(tk.N,tk.W,tk.E,tk.S))
        self.canvas.configure(scrollregion=(0,0,0,self.rows*28+self.bottompadding))
class GUI():
    def __init__(self, master):
        self.root = master
        self.root.title(self.title)
        self.root.resizable(width=False, height=False)
    def center(self):
        self.root.update_idletasks()
        w = self.root.winfo_screenwidth()
        h = self.root.winfo_screenheight()
        size = tuple(int(_) for _ in self.root.geometry().split('+')[0].split('x'))
        x = w/2 - size[0]/2
        y = h/2 - size[1]/2
        self.root.geometry("%dx%d+%d+%d" % (size + (x, y)))
    def run(self):
        self.center()
        self.root.mainloop()
    def createManyVars(self,type,inputArray):
        if type == "Int":
            for i in range(len(inputArray)):
                inputArray[i] = tk.IntVar()
        elif type == "String":
            for i in range(len(inputArray)):
                inputArray[i] = tk.StringVar()
        return inputArray
class photometryGUI(GUI):
    def __init__(self,master):
        self.title = "Photometry Options"
        GUI.__init__(self,master)
        out1, out2 = dirs.readWriteSettings("photometry","read")
        self.photometryConfig1, self.photometryConfig2 = ast.literal_eval(out1), ast.literal_eval(out2)
        self.DataCh, self.trueRefCh, self.isosRefCh = map(int,self.photometryConfig1)
        self.trueRefFreq, self.isosRefFreq = map(int,self.photometryConfig2)
    def initialize(self):
        #variables to hold input
        (Data, trueRef, isosRef, 
            trueRefFreq, isosRefFreq) = (tk.IntVar(), 
            tk.IntVar(), tk.IntVar(), 
            tk.IntVar(), tk.IntVar())
        #Initialize button variables from file:
        self.dataButtons = [Data, trueRef, isosRef]
        for i in range(len(self.dataButtons)):
            self.dataButtons[i].set(self.photometryConfig1[i])
        #initialize frames for buttons
        usrMsg = tk.StringVar()
        label = tk.Label(self.root, textvariable = usrMsg, relief = tk.RAISED)
        usrMsg.set("\nPrevious Settings Loaded\nThese settings will be saved in your .csv outputs.\n")
        label.pack(fill="both",expand="yes")
        DataFrame = tk.LabelFrame(self.root, text="Photometry Data Channel")
        trueRefFrame = tk.LabelFrame(self.root, text="Main Reference Channel")
        isosRefFrame = tk.LabelFrame(self.root, text="Isosbestic Reference Channel")
        dataFrames = [DataFrame, trueRefFrame, isosRefFrame]
        #initialize container boxes for buttons
        R = []
        for i in range(len(dataFrames)):
            R.append(copy.deepcopy([[]]*14))
        for frameIndex in range(len(dataFrames)):
            dataFrames[frameIndex].pack(fill="both",expand="yes")
            for i in range(14):
                R[frameIndex][i] = tk.Radiobutton(dataFrames[frameIndex],text=str(i),
                    variable=self.dataButtons[frameIndex], value = i, 
                    command = lambda (var,i)=(self.dataButtons[frameIndex],frameIndex): self.selectButton(var,i))
                R[frameIndex][i].pack(side=tk.LEFT)
        #initialize fields for frequencies
        dataFields = [trueRefFreq, isosRefFreq]
        frequencyFrame = tk.LabelFrame(self.root, text="Primary & Isosbestic Stimulation Frequencies")
        frequencyFrame.pack(fill="both",expand="yes")
        L1 = tk.Label(frequencyFrame,text="Main Frequency: ")
        L1.pack(side=tk.LEFT)
        self.E1 = tk.Entry(frequencyFrame)
        self.E1.pack(side=tk.LEFT)
        self.E2 = tk.Entry(frequencyFrame)
        self.E2.pack(side=tk.RIGHT)
        L2 = tk.Label(frequencyFrame,text="Isosbestic Frequency: ")
        L2.pack(side=tk.RIGHT)
        self.E1.insert(tk.END,"{}".format(str(self.photometryConfig2[0])))
        self.E2.insert(tk.END,"{}".format(str(self.photometryConfig2[1])))
        #button to exit
        doneButton = tk.Button(self.root,text="Finish",command = self.exitButton)
        doneButton.pack(side=tk.BOTTOM)
    def selectButton(self,var,i):
        self.channelSelected = [self.DataCh, self.trueRefCh, self.isosRefCh]
        if var.get() not in self.channelSelected:
            self.channelSelected[i] = var.get()
        else:
            tempChReport = ["Photometry Data Channel","Main Reference Channel","Isosbestic Reference Channel"]
            tempChReport = tempChReport[self.channelSelected.index(var.get())]
            tkmb.showinfo("Error!", "You already selected \n[Channel {}] \nfor \n[{}]!".format(var.get(),tempChReport))
            self.dataButtons[i].set(self.photometryConfig1[i])
        [self.DataCh, self.trueRefCh, self.isosRefCh] = self.channelSelected
        self.photometryConfig1 = self.channelSelected
    def exitButton(self):
        try:
            self.trueDataFreq = int(self.E1.get())
            self.isosDataFreq = int(self.E2.get())
            if self.trueDataFreq == 0 or self.isosDataFreq == 0:
                tkmb.showinfo("Warning!", "Your frequencies must be higher than 0 Hz!")
            elif self.trueDataFreq == self.isosDataFreq:
                tkmb.showinfo("Warning!", "You should not use the same Frequency for both sample and isosbestic stimulation.")
            else:
                self.photometryConfig2 = self.trueDataFreq, self.isosDataFreq
                self.root.destroy()
                dirs.readWriteSettings("photometry","write",
                    *[str(self.photometryConfig1),str(self.photometryConfig2)])
                self.root.quit()
        except ValueError:
            tkmb.showinfo("Error!", "You must enter integer options into both frequency fields.")
class labJackGUI(GUI):
    def __init__(self,master):
        self.MAX_REQUESTS, self.SMALL_REQUEST = 0, 0
        self.stlFctr, self.ResIndx = 1, 0
        self.ljSaveName = ""
        channels, freq = dirs.readWriteSettings("labJack","read")
        self.chNum, self.scanFreq = ast.literal_eval(channels), int(freq)
        self.nCh, self.chOpt = len(self.chNum), [0]*len(self.chNum)
        self.title = "LabJack Options"
        GUI.__init__(self,master)
        self.updatePresetSaveList()
    def updatePresetSaveList(self):
        self.presetSaveList = []
        dirListing = os.listdir(dirs.prgmDir)
        dirListing.remove("settings.txt")
        for f in dirListing:
            if f.endswith(".txt"):
                self.presetSaveList.append(f[:-4].upper())
    def setup(self):
        leftFrame = tk.LabelFrame(self.root, text="Manual Configuration")
        leftFrame.grid(row=0,column=0)
        rightFrame = tk.LabelFrame(self.root, text="Preset Configuration")
        rightFrame.grid(row=0,column=1)
        ########################################
        #load presets
        usrMsg = tk.StringVar()
        label= tk.Label(rightFrame, textvariable = usrMsg)
        label.pack(fill="both",expand="yes")
        usrMsg.set("\nChoose a Preset\nOr Save a New Preset:")
        existingFrame = tk.LabelFrame(rightFrame, text="Select a Saved Preset")
        existingFrame.pack(fill="both", expand="yes")
        self.presetChosen = tk.StringVar()
        self.presetChosen.set(max(self.presetSaveList, key=len))
        self.savePresetList = tk.OptionMenu(existingFrame,self.presetChosen,*self.presetSaveList,command=self.listChoose)
        self.savePresetList.pack(side=tk.TOP)
        #save new presets
        newPresetFrame = tk.LabelFrame(rightFrame, text="(Optional) Save New Preset:")
        newPresetFrame.pack(fill="both", expand="yes")
        self.newSaveEntry = tk.Entry(newPresetFrame)
        self.newSaveEntry.pack()
        doneButton = tk.Button(newPresetFrame,text="SAVE",command = self.saveButton)
        doneButton.pack()
        ########################################
        #input/view new settings
        usrMsg = tk.StringVar()
        label= tk.Label(leftFrame, textvariable = usrMsg)
        label.pack(fill="both",expand="yes")
        usrMsg.set("\nMost Recently Used Settings:")
        #initialize frames for lj options
        channelFrame = tk.LabelFrame(leftFrame, text = "Channels Selected")
        channelFrame.pack(fill="both",expand="yes")
        checkButtons = [[]]*14
        self.buttonVars = [[]]*14
        self.createManyVars("Int", self.buttonVars)
        for i in range(14):
            checkButtons[i] = tk.Checkbutton(channelFrame, 
                text=printDigits(i,2,placeHolder="0"),
                variable = self.buttonVars[i], onvalue = 1, offvalue = 0,
                command = lambda i=i: self.selectButton(i))
        for i in range(5):
            checkButtons[i].grid(row=0,column=i)
        for i in range(5):
            checkButtons[i+5].grid(row=1,column=i)
        for i in range(4):
            checkButtons[i+5+5].grid(row=2,column=i)
        for i in self.chNum:
            checkButtons[i].select()
        #sampling Freq input options
        scanFrame = tk.LabelFrame(leftFrame, text = "Scan Frequency")
        scanFrame.pack(fill="both",expand="yes")
        L1 = tk.Label(scanFrame,text="Freq/Channel (Hz):")
        L1.pack(side=tk.LEFT)
        self.E1 = tk.Entry(scanFrame,width=8)
        self.E1.pack(side=tk.LEFT)
        self.E1.insert(tk.END,self.scanFreq)
        #button to exit
        doneButton = tk.Button(self.root,text="FINISH",command = self.exitButton)
        doneButton.grid(row=1,column=0,columnspan=2)
        self.run()
    def selectButton(self,i):
        tempChNum = self.chNum
        self.chNum = []
        for i in range(14):
            if self.buttonVars[i].get() == 1:
                self.chNum.append(i)
        self.nCh, self.chOpt = len(self.chNum), [0]*len(self.chNum)
        if self.nCh > 8:
            tkmb.showinfo("Error!", "You cannot use more than 8 LabJack channels at once.")
            self.chNum = tempChNum
            for i in range(14):
                self.buttonVars[i].set(0)
            for i in self.chNum:
                self.buttonVars[i].set(1)
            self.nCh, self.chOpt = len(self.chNum), [0]*len(self.chNum)
        elif self.nCh == 0:
            tkmb.showinfo("Error!", "You must configure at least one channel.")
            self.chNum = tempChNum
            for i in range(14):
                self.buttonVars[i].set(0)
            for i in self.chNum:
                self.buttonVars[i].set(1)
            self.nCh, self.chOpt = len(self.chNum), [0]*len(self.chNum)
    def saveButton(self):
        self.updatePresetSaveList()
        validity = self.checkInputValidity()
        if validity == 1:
            saveName = self.newSaveEntry.get().strip().lower()
            if len(saveName) == 0:
                tkmb.showinfo("Error!", 
                        "You must give your Preset a name.")
            elif len(saveName) != 0:
                if saveName == "settings":
                    tkmb.showinfo("Error!", 
                        "You cannot overwrite the primary [Settings] preset\n\nChoose another name.")
                elif not os.path.isfile(dirs.prgmDir+saveName+".txt"):
                    with open(dirs.prgmDir+saveName+".txt","w") as f:
                        f.write(str(self.chNum)+"\n"+str(self.scanFreq)+"\n")
                        tkmb.showinfo("Saved!", "Preset saved as [{}]".format(saveName.upper()))
                        menu = self.savePresetList.children["menu"]
                        menu.add_command(label=saveName.upper(),
                            command = lambda f=saveName: self.listChoose(f))
                elif os.path.isfile(dirs.prgmDir+saveName+".txt"):
                    if tkmb.askyesno("Overwrite", "[{}] already exists.\nOverwrite this preset?".format(saveName.upper())):
                        with open(dirs.prgmDir+saveName+".txt","w") as f:
                            f.write(str(self.chNum)+"\n"+str(self.scanFreq)+"\n")
                            tkmb.showinfo("Saved!", "Preset saved as [{}]".format(saveName.upper()))
    def exitButton(self):
        validity = self.checkInputValidity()
        if validity == 1:
            self.root.destroy()
            self.root.quit()
    def checkInputValidity(self):
        validity = 0
        try:
            self.scanFreq = int(self.E1.get())
            maxFreq = int(50000/self.nCh)
            if self.scanFreq == 0:
                tkmb.showinfo("Error!", "Scan frequency must be higher than 0 Hz.")
            elif self.scanFreq > maxFreq:
                tkmb.showinfo("Error!", 
                    "SCAN_FREQ x NUM_CHANNELS must be lower than 50,000Hz.\n\nMax [{} Hz] right now with [{}] Channels in use.".format(maxFreq,self.nCh))
            else:
                validity = 1
                dirs.readWriteSettings("labJack","write",
                    *[str(self.chNum),str(self.scanFreq)])
        except ValueError:
            tkmb.showinfo("Error!", "Scan Frequency must be an integer in Hz.")
        return validity
    def listChoose(self,fileName):
        with open(dirs.prgmDir+fileName+".txt") as f:
            self.chNum = map(int,ast.literal_eval(f.readline().strip()))
            self.scanFreq = int(f.readline().strip())
            for i in range(14):
                self.buttonVars[i].set(0)
            for i in self.chNum:
                self.buttonVars[i].set(1)
            self.nCh, self.chOpt = len(self.chNum), [0]*len(self.chNum)
            self.E1.delete(0,"end")
            self.E1.insert(tk.END,self.scanFreq)
class arduinoGUI(GUI):
    def __init__(self,master):
        self.root = master
        self.title = "none"
        GUI.__init__(self,master)
        ##pull last used settings
        self.serPort = dirs.readWriteSettings("serial","read")[0]
        (self.packet,self.tone_pack,self.out_pack,
            self.pwm_pack) = dirs.readWriteSettings("arduino","read")
        [self.packet, self.tone_pack,self.out_pack, self.pwm_pack] = [
        ast.literal_eval(self.packet), 
        ast.literal_eval(self.tone_pack),
        ast.literal_eval(self.out_pack), 
        ast.literal_eval(self.pwm_pack)]
    def setup(self):
        if self.types == "TONE":
            columns = 1
        elif self.types == "OUTPUT":
            columns = 6
        elif self.types == "PWM":
            columns = 5
    def toneSetup(self):
        self.root.title("Tone Configuration")
        numPins, self.numEntries = 1, 15
        scrollFrame = ScrollFrame(self.root,numPins,self.numEntries+1)
        ###buttons
        self.toneButtonVar = tk.IntVar()
        self.toneButtonVar.set(0)
        toneButton = tk.Checkbutton(scrollFrame.topFrame,
            text="Enable Tone (Arduino Pin 10)", variable = self.toneButtonVar,
            onvalue = 1, offvalue = 0, 
            command = lambda tags="tone": self.checkToggle(tags))
        toneButton.pack()
        #entries
        self.entries = []
        for i in range(self.numEntries):
            self.entries.append(copy.deepcopy([copy.deepcopy([])]*3))
        tk.Label(scrollFrame.middleFrame,text="Time On(s)").grid(row=0,column=1)
        tk.Label(scrollFrame.middleFrame,text="Time Off(s)").grid(row=0,column=2)
        tk.Label(scrollFrame.middleFrame,text="Freq(Hz)").grid(row=0,column=3)
        for row in range(self.numEntries):
            tk.Label(scrollFrame.middleFrame,
                text=printDigits(row+1,2,True,"0")).grid(row=row+1,column=0)
            for entryBox in range(3):
                self.entries[row][entryBox] = tk.Entry(
                    scrollFrame.middleFrame, width=7)
                self.entries[row][entryBox].grid(
                    row=row+1,column=entryBox+1)
                self.entries[row][entryBox].config(state=tk.DISABLED)
        #confirm button
        button = tk.Button(scrollFrame.bottomFrame,
            text="Confirm")
        button.pack(side=tk.TOP)
        scrollFrame.finalize()
        self.center()
        root.geometry("257x272")
    def checkToggle(self,tags):
        outputIDs, pwmIDs = ([2,3,4,5,6,7], [8,9,11,12,13])
        if tags == "tone":
            if self.toneButtonVar.get() == 0:
                for entryBox in range(3):
                    for row in range(15):
                        self.entries[row][entryBox].configure(state='disabled')
            elif self.toneButtonVar.get() == 1:
                for entryBox in range(3):
                    for row in range(15):
                        self.entries[row][entryBox].configure(state='normal')
        else:
            if tags in outputIDs:
                i = outputIDs.index(tags)
                var = self.outputButtonVar[i]
            elif tags in pwmIDs:
                i = pwmIDs.index(tags)
                var = self.pwmButtonVar[i]
            if var.get() == 0:
                for entryBox in range(self.numEntries):
                    self.entries[i][entryBox].configure(state='disabled')
            elif var.get() == 1:
                for entryBox in range(self.numEntries):
                    self.entries[i][entryBox].configure(state='normal')
    def outputSetup(self):
        pinIDs = [2,3,4,5,6,7]
        self.root.title("Simple Output Config")
        numPins, self.numEntries = 6, 15
        scrollFrame = ScrollFrame(self.root,numPins,self.numEntries+1,bottompadding=8)
        instructionFrame = tk.LabelFrame(scrollFrame.topFrame,
            text="Enable Arduino Pins")
        instructionFrame.grid(row=0,column=0,sticky=tk.N+tk.E+tk.S+tk.W)
        tk.Label(instructionFrame,
            text=" "*21).pack(side=tk.RIGHT)
        tk.Label(instructionFrame,
            text="Enable pins, then input instructions line by line with comma separation.",
            relief=tk.RAISED).pack(side=tk.RIGHT)
        tk.Label(instructionFrame,
            text=" "*21).pack(side=tk.RIGHT)
        #variables
        self.entries = []
        for pin in range(numPins):
            self.entries.append([])
            for entry in range(self.numEntries):
                self.entries[pin].append([])
        outputButton = [[]]*numPins
        self.outputButtonVar = [[]]*numPins
        self.createManyVars("Int",self.outputButtonVar)
        #setup items
        for pin in range(numPins):
            outputButton[pin] = tk.Checkbutton(
                instructionFrame, 
                text="PIN {}".format(pinIDs[pin]),
                variable=self.outputButtonVar[pin], 
                onvalue=1,offvalue=0,
                command=lambda tags=pinIDs[pin]:self.checkToggle(tags))
            outputButton[pin].pack(side=tk.LEFT)
            tk.Label(scrollFrame.middleFrame,
                text="Pin {}\nTime On(s), Time Off(s)".format(pinIDs[pin])).grid(row=0,column=1+pin)
            for row in range(self.numEntries):
                tk.Label(scrollFrame.middleFrame,
                    text=printDigits(row+1,2,True,"0")).grid(row=row+1,column=0)
                self.entries[pin][row] = tk.Entry(
                    scrollFrame.middleFrame, width=18)
                self.entries[pin][row].grid(
                    row=row+1,column=1+pin)
                self.entries[pin][row].config(state="disabled")
        #confirm button
        button = tk.Button(scrollFrame.bottomFrame,
            text="Confirm")
        button.pack(side=tk.TOP)
        scrollFrame.finalize()
        root.geometry("980x280")
        self.center()
    def pwmSetup(self):
        pinIDs = [8,9,11,12,13]
        self.root.title("PWM Configuration")
        numPins, self.numEntries = 5, 15
        scrollFrame = ScrollFrame(self.root,numPins,self.numEntries+1,bottompadding=24)
        instructionFrame = tk.LabelFrame(scrollFrame.topFrame,
            text="Enable Arduino Pins")
        instructionFrame.grid(row=0,column=0,sticky=tk.N+tk.E+tk.S+tk.W)
        tk.Label(instructionFrame,
            text=" "*6).pack(side=tk.RIGHT)
        tk.Label(instructionFrame,
            text="e.g. 0,180,200,20,90   (Per Entry Box)",
            relief=tk.RAISED).pack(side=tk.RIGHT)
        tk.Label(instructionFrame,
            text=" "*5).pack(side=tk.RIGHT)
        tk.Label(instructionFrame,
            text="Enable pins, then input instructions line by line with comma separation.",
            relief=tk.RAISED).pack(side=tk.RIGHT)
        tk.Label(instructionFrame,
            text=" "*10).pack(side=tk.RIGHT)
        #variables
        self.entries = []
        for pin in range(numPins):
            self.entries.append([])
            for entry in range(self.numEntries):
                self.entries[pin].append([])
        pwmButton = [[]]*numPins
        self.pwmButtonVar = [[]]*numPins
        self.createManyVars("Int",self.pwmButtonVar)
        ##setup items
        for pin in range(numPins):
            pwmButton[pin] = tk.Checkbutton(
                instructionFrame, 
                text="Pin {}".format(pinIDs[pin]),
                variable = self.pwmButtonVar[pin],
                onvalue=1, offvalue=0,
                command=lambda tags=pinIDs[pin]:self.checkToggle(tags))
            pwmButton[pin].pack(side=tk.LEFT)
            tk.Label(scrollFrame.middleFrame,
                text="Pin {}\nOn(s), Off(s), Freq(Hz),\nDuty Cycle (%), Phase Shift (Deg)".format(printDigits(
                        pinIDs[pin],2,True,"0"))).grid(
                            row=0,column=1+pin)
            for row in range(self.numEntries):
                tk.Label(scrollFrame.middleFrame,
                    text=printDigits(row+1,2,True,"0")).grid(row=row+1,column=0)
                self.entries[pin][row] = tk.Entry(
                    scrollFrame.middleFrame, width=25)
                self.entries[pin][row].grid(
                    row=row+1,column=1+pin)
                self.entries[pin][row].config(state="disabled")
        #confirm button
        button = tk.Button(scrollFrame.bottomFrame,
            text="Confirm")
        button.pack(side=tk.TOP)
        scrollFrame.finalize()
        root.geometry("1100x280")
        self.center()





"""
    def outputSetup(self):

    def pwmSetup(self):






        for row in range(100):
            tk.Label(self.frame, text="%s" % row, width=3, borderwidth="1", 
                     relief="solid").grid(row=row, column=0)
            t="this is the second column for row %s" %row
            tk.Label(self.frame, text=t).grid(row=row, column=1)



    def getFileList(self):
        self.presetFileList = []
        if os.path.exists(dirs.presetDir):
            for f in os.listdir(dirs.presetDir):
                if f.endswith(".txt"):
                    self.presetFileList.append(f)
        else:
            os.makedirs(dirs.presetDir)

"""
"""
def get_time():
    global total_time
    while True:
        total_time = (raw_input("How long is the total experiment? Seconds: ")).lower()
        try:
            total_time = int(total_time)*1000
            break
        except ValueError:
            print "You must enter an integer in seconds"
            continue
    return total_time
def get_data_errorCheck(ask_data,types,bestLen,starts,middles,ends,dataHold):
    global total_time
    on, off, on_time, off_time, freq, pins, refr, dutyCycle, phase = [-1]*9
    analysisLoop = 0
    try:
        on, off = int(ask_data.split(",")[0]), int(ask_data.split(",")[1])
        on_time, off_time = on*1000, off*1000
        if types == "tone":
            freq = int(ask_data.split(",")[2])
            refr = freq
        elif types == "output":
            pins = int(ask_data.split(",")[2])
            refr = pins
        if types == "pwm":
            freq = int(ask_data.split(",")[2])
            pins = int(ask_data.split(",")[3])
            dutyCycle = int(ask_data.split(",")[4])
            phase = int(ask_data.split(",")[5])
            refr = long(printDigits(freq,5,True,"0")+printDigits(dutyCycle,5,True,"0")+printDigits(phase,5,True,"0"))
        if (on_time+off_time) > total_time:
            print "\n\n>>>Stimuli time cannot exceed total time of "+str(total_time/1000)+"s."
            analysisLoop = 1
        elif off_time == 0:
            print "\n\n>>>Time interval cannot be 0s!"
            analysisLoop = 1
        elif types == "tone":
            if freq < 50:
                print "\n\n>>>TONE will not function properly with low frequencies."
                print ">>>Use the PWM function instead."
                analysisLoop = 1
        elif types == "output":
            if pins not in [2,3,4,5,6,7]:
                print "\n\n>>>Simple OUTPUTS must use pins 2-7.\n[TRY AGAIN]"
                analysisLoop = 1
        elif types == "pwm":
            if phase not in range(361):
                print "\n\nThe PHASE_SHIFT must be an integer within 360 degrees."
                analysisLoop = 1
            if pins not in [8,9,11,12,13]:
                print "\n\n>>>FREQUENCY_MODULATION must use pins 8 - 13 (10 EXCLUDED)"
                analysisLoop = 1
            elif dutyCycle > 99 or dutyCycle < 1:
                print "\n\n>>>The DUTY_CYCLE_PERCENTAGE must be an integer between 1 and 99"
                analysisLoop = 1
            elif freq > 100:
                print "\n\n>>>It's recommended to use the TONE function for high frequencies."
                print ">>>Alternatively, use an external function generator"
                print "Try Again with a lower frequency (<100Hz)."
                analysisLoop = 1
    except ValueError:
        print "\n\n>>>Did you specify %s INTEGER parameters?" %bestLen
        analysisLoop = 1
    if types == "pwm":
        pinInt = posToInt(pins)
        startsLrg,middlesLrg,endsLrg,dataHoldLrg = starts,middles,ends,dataHold
        try:
            startsLrg[pins], middlesLrg[pins], endsLrg[pins], dataHoldLrg[pinInt]
        except KeyError:
            startsLrg[pins], middlesLrg[pins], endsLrg[pins], dataHoldLrg[pinInt] = {}, {}, {}, {}
        starts, middles, ends, dataHold = startsLrg[pins], middlesLrg[pins], endsLrg[pins], dataHoldLrg[pinInt]
    try:
        starts[refr], middles[refr], ends[refr]
    except KeyError:
        starts[refr], middles[refr], ends[refr] = [], [], []
    if types in ["tone", "pwm"]:
        try:
            dataHold[refr]
        except KeyError:
            dataHold[refr] = []
        startsAll, middlesAll, endsAll = dictFlatten(starts, middles, ends)
    if types == "output":
        startsAll, middlesAll, endsAll = starts[pins], middles[pins], ends[pins]
    if on in startsAll or on+off in endsAll or on in middlesAll or on+off in middlesAll:
        append = ""
        if types in ["pwm", "output"]:
            append = " for PIN %s" %pins
        print "\n\nTime intervals cannot overlap"+append+"!"
        analysisLoop = 1
    if types == "pwm":
        starts,middles,ends,dataHold = startsLrg,middlesLrg,endsLrg,dataHoldLrg
    return on, off, on_time, off_time, freq, pins, analysisLoop, refr, starts, middles, ends, dataHold, dutyCycle, phase
def get_data_invMod(types,dataHold,on_time,off_time,front,back,refr):
    if types in ["pwm", "tone"]:
        if front == 0 and back == 0:
            dataHold[refr].append(on_time)
            dataHold[refr].append(on_time+off_time)
        if front == 1:
            dataHold[refr].remove(on_time)
            dataHold[refr].remove(on_time)
        if back == 1:
            dataHold[refr].remove(on_time+off_time)
            dataHold[refr].remove(on_time+off_time)
    elif types == "output":
        pinInt = posToInt(refr)
        if front == 0 and back == 0:
            if on_time not in dataHold:
                dataHold[on_time] = pinInt
            elif on_time in dataHold:
                dataHold[on_time] += pinInt
            if on_time+off_time not in dataHold:
                dataHold[on_time+off_time] = pinInt
            elif on_time+off_time in dataHold:
                dataHold[on_time+off_time] += pinInt
        if front == 1:
            if dataHold[on_time] == (2*pinInt):
                dataHold.pop(on_time)
            else:
                dataHold[on_time] -= (2*pinInt)
        if back == 1:
            if dataHold[on_time+off_time] == (2*pinInt):
                dataHold.pop(on_time+off_time)
            else:
                dataHold[on_time+off_time] -= (2*pinInt)
    return dataHold
def get_data(types):
    global total_time
    starts, middles, ends, dataHold = {}, {}, {}, {}
    if types in ["tone","output"]:
        name, bestLen = types.upper(), 3
    elif types == "pwm":
        name, bestLen = "FREQUENCY_MODULATION", 6
    gfxSetup(types)
    while True: #mainLoop
        ask_data = raw_input("(type 'done' when finished ["+name+"_SETUP]): ").lower()
        length = len(ask_data.split(","))
        if ask_data == "done":
            break #mainLoop
        elif not length == bestLen:
            print "\n\n>>>Did you specify %s separate parameters?\n[TRY AGAIN]" %bestLen
        else:
            analysisLoop = 0
            while analysisLoop == 0:
                tempHold = get_data_errorCheck(ask_data,types,bestLen,starts,middles,ends,dataHold)
                on, off, on_time, off_time, freq, pins, analysisLoop, refr, starts, middles, ends, dataHold, dutyCycle, phase = tempHold
                if analysisLoop != 0:
                    break #analysisLoop
                if types == "pwm":
                    pinInt = posToInt(pins)
                    startsLrg,middlesLrg,endsLrg,dataHoldLrg = starts, middles, ends, dataHold
                    starts, middles, ends, dataHold = startsLrg[pins], middlesLrg[pins], endsLrg[pins], dataHoldLrg[pinInt]
                middles[refr] += range(on+1, on+off)
                front, back = 0, 0
                dataHold = get_data_invMod(types,dataHold,on_time,off_time,front,back,refr)
                if on in ends[refr] and on+off not in starts[refr]:
                    front, back = 1, 0
                    middles[refr].append(on)
                    ends[refr].remove(on)
                    ends[refr].append(on+off)
                    dataHold = get_data_invMod(types,dataHold,on_time,off_time,front,back,refr) 
                elif on not in ends[refr] and on+off in starts[refr]:
                    front, back = 0, 1
                    middles[refr].append(on+off)
                    starts[refr].remove(on+off)
                    starts[refr].append(on)
                    dataHold = get_data_invMod(types,dataHold,on_time,off_time,front,back,refr)             
                elif on in ends[refr] and on+off in starts[refr]:
                    front, back = 1, 1
                    middles[refr].append(on)
                    middles[refr].append(on+off)
                    starts[refr].remove(on+off)
                    ends[refr].remove(on)
                    dataHold = get_data_invMod(types,dataHold,on_time,off_time,front,back,refr)
                else:
                    starts[refr].append(on)
                    ends[refr].append(on+off)
                if types == "pwm":
                    starts,middles,ends,dataHold = startsLrg,middlesLrg,endsLrg,dataHoldLrg
                analysisLoop = 1 #breaks analysisLoop at very end.
    dataHoldDone = []
    if types == "output":
        dataHoldDone = dataHold
    if types == "tone":
        for freq in dataHold:
            dataHold[freq] = sorted(dataHold[freq])
            for i in range(len(dataHold[freq])):
                if i%2 == 0:
                    dataHoldDone.append([dataHold[freq][i],dataHold[freq][i+1],freq])
    if types == "pwm":
        for pinInt in dataHold:
            for refr in dataHold[pinInt]:
                refri = str(refr)
                freqi, dutyi,phasei = int(refri[:-10]), int(refri[-10:-5]), int(refri[-5:])
                dataHold[pinInt][refr] = sorted(dataHold[pinInt][refr])
                for i in range(len(dataHold[pinInt][refr])):
                    if i%2 == 0:
                        dataHoldDone.append([0,dataHold[pinInt][refr][i],dataHold[pinInt][refr][i+1],freqi,pinInt,phasei,dutyi])
    return dataHoldDone


Loop1 = retrieveSettings(ask_file,allFiles)
def retrieveSettings(ask_file, allFiles):
    Loop1 = 0
    if ask_file == "y":
        print gfxBar(40,1,">>>EXISTING SETTINGS AND DESCRIPTIONS: ")
        for i in allFiles:
            f = open(presetDir+i,"r")
            print "["+i[:-4].upper()+"]: "+f.readline().lower()
            f.close()
        print "#"*30
        print "\nInput one of the above settings to continue."
        Loop2 = 0
        while Loop2 == 0:
            file_name = raw_input("Alternatively, type [exit()] to choose another option: ").lower()
            if file_name == "exit()":
                Loop2 = 1
            elif os.path.isfile(presetDir+file_name+".txt"):
                tempHold = fileMultiRead(file_name,0,packet,tone_pack,out_pack,pwm_pack)
                packet, tone_pack, out_pack, pwm_pack = tempHold
                Loop2 = 1
                Loop1 = 1
            else:
                print "\n>>>You did not enter a correct setting name. Try again."
    elif ask_file == "n":
        print gfxBar(40,1,">>>MANUAL SETUP")
        #total time
        packet[3] = get_time()
        #tone
        tone = get_data("tone")
        packet[4] = len(tone)
        for i in tone:
            tone_pack.append(["<LLH"]+i)
        tone_pack = sorted(tone_pack,key=itemgetter(1))
        #outputs
        output = get_data("output")
        packet[5] = len(output)
        for i in output:
            out_pack.append(["<LB",i,output[i]])
        out_pack = sorted(out_pack,key=itemgetter(1))
        #pwm
        pwm = get_data("pwm")
        packet[6] = len(pwm)
        for i in pwm:
            pwm_pack.append(["<LLLfBBf"]+i)
        pwm_pack = sorted(pwm_pack,key=itemgetter(2))
        #
        Loop3 = 0
        while Loop3 == 0:
            ask_save = raw_input("\n\n\n\n>>>Save these Settings? (Y/N): ").lower()
            if ask_save == "y":
                Loop4 = 0
                while Loop4 == 0:
                    ask_name = raw_input("Give this setting a name: ").lower()
                    if ask_name == "exit()":
                        print "\nYou cannot use the [exit()] code as a name. \nTry again."
                    elif not os.path.isfile(presetDir+ask_name+".txt"):
                        ask_descrp = raw_input("...and a description:\n>>>").lower()
                        print "\nSaving..."
                        fileMultiWrite(ask_name,ask_descrp,packet,tone_pack,out_pack,pwm_pack)
                        time.sleep(0.2)
                        print "New Settings saved to "+presetDir
                        Loop4 = 1
                        Loop3 = 1
                        Loop1 = 1
                    elif os.path.isfile(presetDir+ask_name+".txt"):
                        print "\n'%s' already exists as a setting!" %ask_name
                        Loop5 = 0
                        while Loop5 == 0:
                            ask_ovrWrt = raw_input("Overwrite this setting name anyway? (Y/N): ").lower()
                            if ask_ovrWrt == "y":
                                ask_descrp = raw_input("\nGive this setting a new description:\n>>> ").lower()
                                print "\nSaving..."
                                fileMultiWrite(ask_name,ask_descrp,packet,tone_pack,out_pack,pwm_pack)
                                time.sleep(0.2)
                                print "Overwritten to "+presetDir
                                Loop5 = 1
                                Loop4 = 1
                                Loop3 = 1
                                Loop1 = 1
                            elif ask_ovrWrt == "n":
                                Loop5 = 1
                            else:
                                print "Type Y/N to Continue"
            elif ask_save == "n":
                print "\n\nSettings were not saved.\n\n"
                Loop3 = 1
                Loop1 = 1
            else:
                print "Type (Y/N) to Continue."
    else:
        print "Type (Y/N) to Continue."
    return Loop1





    global total_time,serPort,baudRate,ser,mainLoopbrk,expName
                
            print gfxBar(40,1,">>>CURRENTLY SELECTED SETTINGS: ")
            timeSegment = float(packet[3]/100)
            print "(Note that the following graphical representation has an error within +/- [1 segment], or ["+str(timeSegment/1000)+"s]."
            print "Accurate timings are listed on the right)\n"
            print "Each segment represents " + str((timeSegment/1000))+"s"
            print "-"*100+" [TOTAL TIME]: [" +str(packet[3]/1000) +"s]"
            print " "*101+"|  ON -  OFF|PIN|Freq-DtyCycl-PhsShft|"
            gfxTimeDisplay("tones",tone_pack,timeSegment)
            gfxTimeDisplay("simple outputs",out_pack,timeSegment)
            gfxTimeDisplay("frequency modulated outputs",pwm_pack,timeSegment)
            print gfxBar(1)
            Loop6 = 0
            while Loop6 == 0:
                ask_proceed = raw_input("\nAre these settings correct? (Y/N): ").lower()
                if ask_proceed == "y":
                    Loop6 = 1
                    setupMainLoop = 1
                elif ask_proceed == "n":
                    print "Clearing...\nPerforming Setup Sequence again..."
                    Loop6 = 1
                    time.sleep(0.5)
                else:
                    print "Type (Y/N) to Continue."
    elif settings == "use_old":
        pass
    expName = raw_input("\n>>>Give this trial an identifying name (e.g. HRHR; GCaMP-1; etc.):\n")
"""





#####
#Misc. Usefuls
def printDigits(num,places,front=True,placeHolder=" "):
    if front:
        return placeHolder*(places-len(str(num)))+str(num)
    elif not front:
        return str(num)+placeHolder*(places-len(str(num)))
def printMinFromSec(secs,ms=False):
    sec = int(secs)%60
    mins = int(secs)//60
    if ms:
        millis = int((secs - int(secs))*1000)
        return "{}:{}.{}".format(printDigits(mins,2,True,"0"),
            printDigits(sec,2,True,"0"),printDigits(millis,3,True,"0"))
    elif not ms:
        return "{}:{}".format(printDigits(mins,2,True,"0"),
            printDigits(sec,2,True,"0"))
def getDay(options=0):
    i = datetime.now()
    hour = printDigits(i.hour,2,True,"0")
    minute = printDigits(i.minute,2,True,"0")
    second = printDigits(i.second,2,True,"0")
    if options == 0:
        return "%s/%s/%s" % (i.year,i.month,i.day)
    elif options == 1:
        return "%s-%s-%s [%s-%s-%s]" % (i.year,i.month,i.day,hour,minute,second)
    elif options == 2:
        return "%s-%s-%s" % (i.year,i.month,i.day)
    elif options == 3:
        if i.hour > 12:
            hour = str(i.hour-12)+"pm"
        if i.hour == 12:
            hour = "12pm"
        if i.hour < 12:
            hour = str(i.hour)+"am"
        if i.hour == 0:
            hour = "12am"
        return "%s-%s-%s" % (hour,minute,second)
def checkBin(a,register):
    if register == "D":
        dicts = {1:0, 2:1, 4:2, 8:3, 16:4, 32:5, 64:6, 128:7}
    elif register == "B":
        dicts = {1:8, 2:9, 4:10, 8:11, 16:12, 32:13}
    store = []
    for i in dicts:
        if a&i > 0:
            store.append(dicts[i])
    return store
def deepCopyLists(outer,inner):
    hold = []
    for i in range(outer):
        hold.append(copy.deepcopy([copy.deepcopy([])]*inner))
    return hold
def presetRead(fileName):
    with open(dirs.presetDir+fileName+".txt") as f:
        hold = []
        for i in range(4):
            hold.append(f.readline())
    return hold
class progressBar(threading.Thread):
    def __init__(self, canvas, bar, time, buttonOn, buttonOff, msTotalTime):
        threading.Thread.__init__(self)
        self.canvas = canvas
        self.segmentSize = (float(msTotalTime/1000))/1000
        self.msTotalTime = msTotalTime
        self.bar = bar
        self.time = time
        self.running = False
        self.numProg,self.numTime = 1,1
        self.buttonOn = buttonOn
        self.buttonOff = buttonOff
        self.timeDiff = 0
    def advance(self):
        while self.running:
            now = datetime.now()
            self.timeDiff = (now-self.startProg).seconds+float((now-self.startProg).microseconds)/1000000
            if self.timeDiff/self.numTime >= 0.005:
                self.canvas.itemconfig(self.time,text="{}".format(printMinFromSec(self.timeDiff,True)))
                self.numTime+=1
            if self.timeDiff/self.numProg >= self.segmentSize:
                self.canvas.move(self.bar,1,0)
                if (self.numProg > 35) and (self.numProg < 965):
                    self.canvas.move(self.time,1,0)
                self.numProg += 1
            self.canvas.update()
            time.sleep(0.005)
            if self.numProg > 1000 or self.timeDiff>float(self.msTotalTime/1000):
                self.running = False
                self.buttonOn.config(state="normal")
                self.buttonOff.config(state="disabled")
    def start(self):
        if self.numProg != 1:
            self.canvas.move(self.bar,-self.numProg+1,0)
            if (-self.numProg+1+35) < 0:
                textMove = max(-self.numProg+1+35,-929)
                self.canvas.move(self.time,textMove,0)
            self.numProg, self.numTime = 1, 1
        self.startProg = datetime.now()
        self.running = True
        self.buttonOn.config(state="disabled")
        self.buttonOff.config(state="normal")
        self.advance()
    def stop(self):
        self.buttonOn.config(state="normal")
        self.buttonOff.config(state="disabled")
        self.running = False




#####
#Directories
class dirs():
    def __init__(self):
        self.userhome = os.path.expanduser('~')
        self.baseDir = self.userhome+"/desktop/arduinoControl/"
        self.presetDir = self.baseDir+"UserPresets/"
        self.prgmDir = self.baseDir+"prgmSettings/"
        self.saveDir = self.baseDir+"outputSaves/"
        self.resultsDir = ""
    def setupMainDirs(self):
        if not os.path.exists(self.prgmDir):
            os.makedirs(self.prgmDir)
            #Create default examples
            with open(self.prgmDir+"example preset.txt","w") as f:
                f.write("[0,1,2,3]\n")
                f.write("5000\n")
        if not os.path.isfile(self.prgmDir+"settings.txt"):
            #Just in case settings.txt is deleted but not prgmDir:
            #we will make settings.txt anyway
            with open(self.prgmDir+"settings.txt","w") as f:
                #these are example presets
                f.write("/dev/cu.usbmodem1421\n")
                f.write("[0,2]\n")
                f.write("20000\n")
                f.write("[0,1,2]\n")
                f.write("[0,0]\n")
                f.write("['<BBLHHH', 255, 255, 180000, 1, 2, 0]\n")
                f.write("[['<LLH', 120000, 150000, 2800]]\n")
                f.write("[['<LB', 148000, 4], ['<LB', 150000, 4]]\n")
                f.write("[]\n")
                f.write("Tiange\n")
        if not os.path.exists(self.presetDir):
            os.makedirs(self.presetDir)
            #Create default examples
            f = open(self.presetDir+"example.txt","w")
            f.write("['<BBLHHH', 255, 255, 180000, 1, 2, 0]\n")
            f.write("[['<LLH', 120000, 150000, 2800]]\n")
            f.write("[['<LB', 148000, 4], ['<LB', 150000, 4]]\n")
            f.write("[]\n")
            f.close()
        if not os.path.exists(self.saveDir):
            os.makedirs(self.saveDir+"Tiange/")
    def readWriteSettings(self,typeRequired,readWrite,*args):
        #RETURNS LISTS OF STRINGS
        #CONVERT LOCALLY TO FORMAT REQUIRED!
        if typeRequired == "serial":
            lines = [0]
        elif typeRequired == "labJack":
            lines = [1,2]
        elif typeRequired == "photometry":
            lines = [3,4]
        elif typeRequired == "arduino":
            lines = [5,6,7,8]
        elif typeRequired == "saveName":
            lines = [9]
        numLines = 10
        if readWrite == "read":
            hold = []
            with open(self.prgmDir+"settings.txt","r") as f:
                for i in range(numLines):
                    hold.append(f.readline().strip())
            return hold[lines[0]:lines[-1]+1]
        if readWrite == "write":
            with open(self.prgmDir+"settings.txt","r") as f:
                hold = []
                for i in range(numLines):
                    hold.append(f.readline())
            for i in range(len(lines)):
                hold[lines[i]] = args[i].strip()+"\n"
            with open(self.prgmDir+"settings.txt","w") as f:
                for i in range(numLines):
                    f.write(hold[i])

#####
#Arduino Related


#####
#Labjack related
class LJU6(u6.U6):
    def streamConfig(self, NumChannels = 1, ResolutionIndex = 0, 
        SamplesPerPacket = 25, SettlingFactor = 0, 
        InternalStreamClockFrequency = 0, DivideClockBy256 = False, 
        ScanInterval = 1, ChannelNumbers = [0], ChannelOptions = [0], 
        ScanFrequency = None, SampleFrequency = None):
        if NumChannels != len(ChannelNumbers) or NumChannels != len(ChannelOptions):
            raise LabJackException("NumChannels must match length of ChannelNumbers and ChannelOptions")
        if len(ChannelNumbers) != len(ChannelOptions):
            raise LabJackException("len(ChannelNumbers) doesn't match len(ChannelOptions)")
        if (ScanFrequency is not None) or (SampleFrequency is not None):
            if ScanFrequency is None:
                ScanFrequency = SampleFrequency
            if ScanFrequency < 1000:
                if ScanFrequency < 25:
                    SamplesPerPacket = self.findSamplesPerPacket(ScanFrequency,NumChannels) #below 25 ScanFreq, S/P is some multiple of nCh less than SF.
                DivideClockBy256 = True
                ScanInterval = 15625/ScanFrequency
            else:
                DivideClockBy256 = False
                ScanInterval = 4000000/ScanFrequency
        ScanInterval = min( ScanInterval, 65535 )
        ScanInterval = int( ScanInterval )
        ScanInterval = max( ScanInterval, 1 )
        SamplesPerPacket = max( SamplesPerPacket, 1)
        SamplesPerPacket = int( SamplesPerPacket )
        SamplesPerPacket = min ( SamplesPerPacket, 25)
        command = [ 0 ] * (14 + NumChannels*2)
        #command[0] = Checksum8
        command[1] = 0xF8
        command[2] = NumChannels+4
        command[3] = 0x11
        #command[4] = Checksum16 (LSB)
        #command[5] = Checksum16 (MSB)
        command[6] = NumChannels
        command[7] = ResolutionIndex
        command[8] = SamplesPerPacket
        #command[9] = Reserved
        command[10] = SettlingFactor
        command[11] = (InternalStreamClockFrequency & 1) << 3
        if DivideClockBy256:
            command[11] |= 1 << 1
        t = struct.pack("<H", ScanInterval)
        command[12] = ord(t[0])
        command[13] = ord(t[1])
        for i in range(NumChannels):
            command[14+(i*2)] = ChannelNumbers[i]
            command[15+(i*2)] = ChannelOptions[i]
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
        
        if SamplesPerPacket < 25: #Only happens for ScanFreq < 25, in which case this number is generated as described above
            self.packetsPerRequest = 1
        elif SamplesPerPacket == 25: #For all ScanFreq > 25. 
            self.packetsPerRequest = self.findPacketsPerRequest(ScanFrequency, NumChannels)
            #Such that PacketsPerRequest*SamplesPerPacket % NumChannels == 0, where min P/R is 1 and max 48 for nCh 1-6,8 
            # and max 42 for nCh 7. 
        self.packsPerReq, self.smplsPerPack = self.packetsPerRequest, SamplesPerPacket
    def findPacketsPerRequest(self,scanFreq,nCh):
        if nCh == 7:
            high = 42
        else:
            high = 48
        hold = []
        for i in range(scanFreq+1):
            if i%25 == 0 and i%nCh == 0:
                hold.append(i)
        hold = np.asarray(hold)
        hold = min(high,max(hold/25))
        hold = max(1,hold)
        return hold
    def findSamplesPerPacket(self,scanFreq,nCh):
        hold = []
        for i in range(scanFreq+1):
            if i%nCh==0:
                hold.append(i)
        return max(hold)

#####




#####
#Camera Related



cameraSaveName = ""



##############################################################################################################
#=================================================PROGRAM====================================================#
##############################################################################################################
dirs = dirs()
dirs.setupMainDirs()



class masterGUI:
    def __init__(self,master):
        self.singleWidgetDim = 100
        self.master = master
        self.master.title("Fear Control")
        self.master.resizable(width=False, height=False)
        self.timeLabelFont = tkFont.Font(family="Helvetica", size=9)
        self.labelFont = tkFont.Font(family="Helvetica", size=11)
        self.labelFontSymbol = tkFont.Font(family="Helvetica", size=10)
        self.balloon = Pmw.Balloon(master)
        #########################################
        #Give each setup GUI its own box
        ####
    #photometry config
        #frame
        photometryFrame = tk.LabelFrame(self.master,
            text="Optional Photometry Config.",
            width = self.singleWidgetDim*2, height = self.singleWidgetDim,highlightthickness=5)
        photometryFrame.grid(row=0,column=0,sticky=tk.W+tk.E+tk.N+tk.S)
        #var
        self.photometryBool = tk.IntVar()
        self.photometryBool.set(0)
        self.photometryString = tk.StringVar()
        self.photometryString.set("\n[N/A]")
        #buttons
        self.photometryCheck = tk.Checkbutton(photometryFrame,
            text="Toggle Photometry On/Off",
            variable=self.photometryBool, onvalue=1, offvalue=0,
            command=self.photometryOnOff)
        self.photometryCheck.pack()
        self.startGUIButton = tk.Button(photometryFrame,text="CONFIG",
            command = self.photometryConfig)
        self.startGUIButton.pack()
        self.startGUIButton.config(state="disabled")
        self.photometryLabel = tk.Label(photometryFrame,textvariable=self.photometryString)
        self.photometryLabel.pack()
        #########################################
    #save file config
        self.grabSaveList()
        #main save frame
        saveFileFrame = tk.LabelFrame(self.master,
            text="Data Output Save Location",
            width = self.singleWidgetDim*2, height = self.singleWidgetDim,highlightthickness=5)
        saveFileFrame.grid(row=1, column=0, columnspan=1,sticky=tk.W+tk.E+tk.N+tk.S)
        #display save name chosen
        self.saveFileName = tk.StringVar()

        saveFileLabel = tk.Label(saveFileFrame,textvariable=self.saveFileName,relief=tk.RAISED)
        saveFileLabel.pack(side=tk.TOP,expand="yes",fill="both")
        #secondary save frames: /existing saves
        existingSaveFrame = tk.LabelFrame(saveFileFrame, text="Select a Save Name")
        existingSaveFrame.pack(fill="both", expand="yes")
        self.dirChosen = tk.StringVar()
        lastUsed = dirs.readWriteSettings("saveName","read")[0]
        self.saveFileName.set("\nLast Used Save Dir.:\n[{}]".format(lastUsed))
        self.dirChosen.set("{: <25}".format(lastUsed.upper()))        
        self.saveDirListMenu = tk.OptionMenu(existingSaveFrame,self.dirChosen,
            *self.saveDirList,command=self.saveButtonOptions)
        self.saveDirListMenu.config(width=20)
        self.saveDirListMenu.grid(sticky = tk.W+tk.E+tk.N+tk.S, columnspan=2)
        #secondary save frames: /new saves
        newSaveFrame = tk.LabelFrame(saveFileFrame, text="Create a New Save Location")
        newSaveFrame.pack(fill="both", expand="yes")
        self.newSaveEntry = tk.Entry(newSaveFrame)
        self.newSaveEntry.pack(side=tk.TOP)
        newSaveButton = tk.Button(newSaveFrame,text="Create New",command=lambda:self.saveButtonOptions("**new**save**&!@"))
        newSaveButton.pack(side=tk.TOP)
        ######################
        ######
    #labjack config
        #frame
        ljFrame = tk.LabelFrame(self.master,
            text="LabJack Config.",
            width=self.singleWidgetDim*2, height = self.singleWidgetDim,highlightthickness=5)
        ljFrame.grid(row=2,column=0,sticky=tk.W+tk.E+tk.N+tk.S)
        #vars
        self.ljString = tk.StringVar()
        channels, freq = dirs.readWriteSettings("labJack","read")
        self.ljString.set("Channels:\n{}\n\nScan Freq: [{}Hz]".format(channels,freq))
        #current state string
        self.ljLabel = tk.Label(ljFrame, textvariable=self.ljString)
        self.ljLabel.grid(row=0,column=0,columnspan=2,sticky=tk.W+tk.E+tk.N+tk.S)
        #config button
        self.ljConfigButton = tk.Button(ljFrame, text="CONFIG",
            command = self.ljConfig)
        self.ljConfigButton.grid(row=1,column=0,sticky=tk.W+tk.E+tk.N+tk.S)
        self.ljTestButton = tk.Button(ljFrame, text="Test LabJack",
            command = self.ljTest)
        self.ljTestButton.grid(row=1,column=1,sticky=tk.W+tk.E+tk.N+tk.S)
    #arduino config
        #frame
        self.ardBackgroundHeight = 260
        ardFrame = tk.LabelFrame(self.master,
            text = "Arduino Stimuli Config.",
            width = self.singleWidgetDim*11,height = self.ardBackgroundHeight)
        ardFrame.grid(row=0,rowspan=3,column=1,sticky=tk.W+tk.N+tk.S)
        tk.Label(ardFrame,
            text="Last used settings shown. Rollover individual segments for specific stimuli config information.",
            relief=tk.RAISED).grid(row=0,columnspan=1, sticky=tk.W+tk.E+tk.N+tk.S)
        #main progress canvas
        self.ardCanvas = tk.Canvas(ardFrame, width = 1050, height = self.ardBackgroundHeight+10)
        self.ardCanvas.grid(row=1,column=0)
        self.canvasInitialize()
        #progress bar control buttons
        self.progButtonOn = tk.Button(ardFrame,text="START")
        self.progButtonOn.grid(row=2,column=0,stick=tk.W)
        self.progButtonOff = tk.Button(ardFrame,text="STOP")
        self.progButtonOff.grid(row=3,column=0,stick=tk.W)
        #grab data and generate progress bar
        self.grabArdData()
        #arduino presets
        self.updateArdPresetSaveList()
        self.ardPresetChosen = tk.StringVar()
        self.ardPresetChosen.set("{: <40}".format("(select a preset)"))
        self.ardPresetMenu = tk.OptionMenu(ardFrame,self.ardPresetChosen,
            *self.ardPresetSaveList,
            command= lambda file: self.grabArdData(True,file))
        self.ardPresetMenu.grid(row=4,column=0,sticky=tk.W)
    #update window
        self.updateWindow()
    def updateArdPresetSaveList(self):
        self.ardPresetSaveList = []
        dirListing = os.listdir(dirs.presetDir)
        for f in dirListing:
            if f.endswith(".txt"):
                self.ardPresetSaveList.append(f[:-4].upper())
    def canvasInitialize(self):
        #progressbar backdrop
        self.ardCanvas.create_rectangle(0,0, 1050,self.ardBackgroundHeight, fill="black",outline="black")
        self.ardCanvas.create_rectangle(0,35-1, 1050, 35+1, fill="white")
        self.ardCanvas.create_rectangle(0,155-1, 1050, 155+1, fill="white")
        self.ardCanvas.create_rectangle(0,15-1, 1050, 15+1, fill="white")
        self.ardCanvas.create_rectangle(0,self.ardBackgroundHeight-5-1,1050, self.ardBackgroundHeight-5+1, fill="white")
        self.ardCanvas.create_rectangle(0,15, 0, self.ardBackgroundHeight-5,fill="white",outline="white")
        self.ardCanvas.create_rectangle(1000,15, 1013, self.ardBackgroundHeight-5,fill="white",outline="white")
            #some labels for each segment
        self.ardCanvas.create_rectangle(1000,0, 1013, 15,fill="black")
        self.ardCanvas.create_text(1000+7,15+10,text=u'\u266b',fill="black")
        self.ardCanvas.create_rectangle(1000,35, 1013, 35,fill="black")
        self.ardCanvas.create_text(1000+7,35+10,text="S",fill="black")
        self.ardCanvas.create_text(1000+7,55+10,text="I",fill="black")
        self.ardCanvas.create_text(1000+7,75+10,text="M",fill="black")
        self.ardCanvas.create_text(1000+7,95+10,text="P",fill="black")
        self.ardCanvas.create_text(1000+7,115+10,text="L",fill="black")
        self.ardCanvas.create_text(1000+7,135+10,text="E",fill="black")
        self.ardCanvas.create_rectangle(1000,155, 1013, 155,fill="black")
        self.ardCanvas.create_text(1000+7,175+10,text="P",fill="black")
        self.ardCanvas.create_text(1000+7,195+10,text="W",fill="black")
        self.ardCanvas.create_text(1000+7,215+10,text="M",fill="black")
        self.ardCanvas.create_rectangle(1000,self.ardBackgroundHeight-5, 1013,self.ardBackgroundHeight,fill="black")
            #label pins as well
        self.ardCanvas.create_text(1027+6,9,text="PINS",fill="white")
        self.ardCanvas.create_text(1027+6,15+10,text="10",fill="white")
        self.ardCanvas.create_text(1027+6,35+10,text="02",fill="white")
        self.ardCanvas.create_text(1027+6,55+10,text="03",fill="white")
        self.ardCanvas.create_text(1027+6,75+10,text="04",fill="white")
        self.ardCanvas.create_text(1027+6,95+10,text="05",fill="white")
        self.ardCanvas.create_text(1027+6,115+10,text="06",fill="white")
        self.ardCanvas.create_text(1027+6,135+10,text="07",fill="white")
        self.ardCanvas.create_text(1027+6,155+10,text="08",fill="white")
        self.ardCanvas.create_text(1027+6,175+10,text="09",fill="white")
        self.ardCanvas.create_text(1027+6,195+10,text="11",fill="white")
        self.ardCanvas.create_text(1027+6,215+10,text="12",fill="white")
        self.ardCanvas.create_text(1027+6,235+10,text="13",fill="white")
    def grabArdData(self,destroy=False,loadFromFile=False):
        #(packet,tone_pack,out_pack,pwm_pack)
        if loadFromFile is not False:
            tempHold = presetRead(loadFromFile)
            dirs.readWriteSettings("arduino","write",*tempHold)
        if destroy:
            self.ardCanvas.delete(self.progressShape)
            self.ardCanvas.delete(self.progressText)
            for i in self.vertBars:
                self.ardCanvas.delete(i)
            for i in self.barTimes:
                self.ardCanvas.delete(i)
            for i in self.toneBars:
                self.balloon.tagunbind(self.ardCanvas,i)
                self.ardCanvas.delete(i)
            for i in self.outBars:
                self.balloon.tagunbind(self.ardCanvas,i)
                self.ardCanvas.delete(i)
            for i in self.pwmBars:
                self.balloon.tagunbind(self.ardCanvas,i)
                self.ardCanvas.delete(i)
        self.ardData = arduinoGUI(tk.Toplevel())
        self.ardData.root.destroy()
        divisor = 5+5*int(self.ardData.packet[3]/300000)
        segment = float(self.ardData.packet[3]/1000)/divisor
        self.vertBars = [[]]*(1+int(round(segment)))
        self.barTimes = [[]]*(1+int(round(segment)))
        for i in range(int(round(segment))):
            if i > 0:
                if i%2 != 0:
                    self.vertBars[i] = self.ardCanvas.create_rectangle(i*(1000.0/segment)-1,15, 
                        i*(1000.0/segment)+1, self.ardBackgroundHeight-5, 
                        fill="white")
                if i%2 == 0:
                    self.vertBars[i] = self.ardCanvas.create_rectangle(i*(1000.0/segment)-1,15, 
                        i*(1000.0/segment)+1, self.ardBackgroundHeight, 
                        fill="white")
                    self.barTimes[i] = self.ardCanvas.create_text(i*(1000.0/segment),self.ardBackgroundHeight+8,
                        text=printMinFromSec(divisor*i),fill="black",font=self.timeLabelFont)
                if i == int(round(segment))-1 and (i+1)%2 == 0 and (i+1)*(1000.0/segment)<=1001:
                    if round((i+1)*(1000.0/segment)) != 1000.0:
                        self.vertBars[i+1] = self.ardCanvas.create_rectangle((i+1)*(1000.0/segment)-1,15, 
                            (i+1)*(1000.0/segment)+1, self.ardBackgroundHeight, 
                            fill="white")
                    elif round((i+1)*(1000.0/segment)) == 1000:
                        self.vertBars[i+1] = self.ardCanvas.create_rectangle((i+1)*(1000.0/segment)-1,self.ardBackgroundHeight-5, 
                            (i+1)*(1000.0/segment)+1, self.ardBackgroundHeight, 
                            fill="white")
                    self.barTimes[i+1] = self.ardCanvas.create_text((i+1)*(1000.0/segment),self.ardBackgroundHeight+8,
                        text=printMinFromSec(divisor*(i+1)),fill="black",font=self.timeLabelFont)
                if i == int(round(segment))-1 and (i+1)%2 != 0 and (i+1)*(1000.0/segment)<=1001:
                    if round((i+1)*(1000.0/segment)) != 1000.0:
                        self.vertBars[i+1] = self.ardCanvas.create_rectangle((i+1)*(1000.0/segment)-1,15, 
                            (i+1)*(1000.0/segment)+1, self.ardBackgroundHeight, 
                            fill="white")
                    elif round((i+1)*(1000.0/segment)) == 1000:
                        self.vertBars[i+1] = self.ardCanvas.create_rectangle((i+1)*(1000.0/segment)-1,self.ardBackgroundHeight-5, 
                            (i+1)*(1000.0/segment)+1, self.ardBackgroundHeight, 
                            fill="white")
        self.toneData, self.outData, self.pwmData = -1, -1, -1
        self.toneBars = []
        if len(self.ardData.tone_pack) != 0:
            self.toneData = self.decodeArdData("tone",self.ardData.tone_pack)
            self.toneBars = [[]]*len(self.toneData)
            for i in range(len(self.toneData)):
                self.toneBars[i] = self.ardCanvas.create_rectangle(self.toneData[i][0],0+15, 
                    self.toneData[i][1]+self.toneData[i][0], 35, fill="yellow",outline="white")
                self.balloon.tagbind(self.ardCanvas,self.toneBars[i],
                    "{} - {}\n{} Hz".format(printMinFromSec(
                        self.toneData[i][4]/1000), printMinFromSec(self.toneData[i][5]/1000), 
                        self.toneData[i][3]))
        self.outBars = []
        if len(self.ardData.out_pack) != 0:
            pinIDs = [2,3,4,5,6,7]
            self.outData = self.decodeArdData("output",self.ardData.out_pack)
            self.outBars = [[]]*len(self.outData)
            for i in range(len(self.outData)):
                yPosition = 35+(pinIDs.index(self.outData[i][3]))*20
                self.outBars[i] = self.ardCanvas.create_rectangle(self.outData[i][0],yPosition, 
                    self.outData[i][1]+self.outData[i][0], yPosition+20, fill="yellow",outline="white")
                self.balloon.tagbind(self.ardCanvas,self.outBars[i],
                    "{} - {}\nPin {}".format(printMinFromSec(
                        self.outData[i][4]/1000), printMinFromSec(self.outData[i][5]/1000), 
                        self.outData[i][3]))
        self.pwmBars = []
        if len(self.ardData.pwm_pack) != 0:
            pinIDs = [8,9,11,12,13]
            self.pwmData = self.decodeArdData("pwm",self.ardData.pwm_pack)
            self.pwmBars = [[]]*len(self.pwmData)
            for i in range(len(self.pwmData)):
                yPosition = 155+(pinIDs.index(self.pwmData[i][3]))*20
                self.pwmBars[i] = self.ardCanvas.create_rectangle(self.pwmData[i][0],yPosition, 
                    self.pwmData[i][1]+self.pwmData[i][0], yPosition+20, fill="yellow",outline="white")
                self.balloon.tagbind(self.ardCanvas,self.pwmBars[i],
                    ("{} - {}\nPin {}\nFreq: {}Hz\nDuty Cycle: {}%\nPhase Shift: {}"+u'\u00b0').format(
                        printMinFromSec(self.pwmData[i][7]/1000), 
                        printMinFromSec(self.pwmData[i][8]/1000), 
                        self.pwmData[i][3],self.pwmData[i][4],self.pwmData[i][5],self.pwmData[i][6]))
        self.progressShape = self.ardCanvas.create_rectangle(
            -1,0,1,self.ardBackgroundHeight, fill="red")
        self.progressText = self.ardCanvas.create_text(35,0,
            fill="white",anchor=tk.N)
        progBar = progressBar(self.ardCanvas, 
            self.progressShape, self.progressText, self.progButtonOn,
            self.progButtonOff, self.ardData.packet[3])
        self.progButtonOn.config(command = progBar.start)
        self.progButtonOff.config(state="disabled",command=progBar.stop)
    def decodeArdData(self,name,dataSource):
        timeSegment = float(self.ardData.packet[3])/1000
        if name == "tone":
            start, on = 1, 2
        elif name == "pwm":
            start, on = 2, 3
        elif name == "output":
            indivTriggers, indivTimes, triggerTimes, finalInterval = [], [], {}, []
            start, on, = 1, 2
            for i in dataSource:
                triggers = checkBin(i[2],"D")
                for n in triggers:
                    indivTriggers.append(n)
                    indivTimes.append(i[1])
            for i in range(len(indivTriggers)):
                n = indivTriggers[i]
                try:
                    triggerTimes[n].append(indivTimes[i])
                except KeyError:
                    triggerTimes[n] = [indivTimes[i]]
            for i in triggerTimes:
                for n in range(len(triggerTimes[i])):
                    if n%2==0:
                        finalInterval.append([i,triggerTimes[i][n],triggerTimes[i][n+1]])
            finalInterval = sorted(finalInterval,key=itemgetter(1))
            dataSource = finalInterval
        ardData = []
        for i in dataSource:
            startSpace = (float(i[start])/timeSegment)
            onSpace = float(i[on])/timeSegment-startSpace
            if onSpace == 0:
                startSpace = startSpace - 1
                onSpace = 1
            offSpace = 1000-onSpace-startSpace
            if name == "tone":
                ardData.append([startSpace,onSpace,offSpace,i[3],i[start],i[on]])
            elif name == "pwm":
                ardData.append([startSpace,onSpace,offSpace,
                    checkBin(i[5],"B")[0],i[4],i[7],i[6],i[start],i[on]])
            elif name == "output":
                ardData.append([startSpace,onSpace,offSpace,i[0],i[start],i[on]])
        return ardData
    def updateWindow(self):
        self.master.update_idletasks()
        w = self.master.winfo_screenwidth()
        h = self.master.winfo_screenheight()
        size = tuple(int(_) for _ in self.master.geometry().split('+')[0].split('x'))
        x = w/2 - size[0]/2
        y = h/2 - size[1]/2
        self.master.geometry("%dx%d+%d+%d" % (size + (x, y)))
    def photometryOnOff(self):
        if self.photometryBool.get() == 1:
            self.startGUIButton.config(state="normal")
            channels, freq = dirs.readWriteSettings("photometry","read")
            state = "Channels: {}\nScan Freq: {}".format(channels,
                    list(ast.literal_eval(freq)))
            self.photometryString.set(state)
        elif self.photometryBool.get() == 0:
            self.startGUIButton.config(state="disabled")
            self.photometryString.set("\n[N/A]")
    def photometryConfig(self):
        config = tk.Toplevel(self.master)
        configRun = photometryGUI(config)
        configRun.initialize()
        configRun.run()
        state = "Channels: {}\nScan Freq: {}".format(configRun.photometryConfig1,
            list(configRun.photometryConfig2))
        self.photometryString.set(state)
    def grabSaveList(self):
        self.saveDirList = [d.upper() for d in os.listdir(dirs.saveDir) if os.path.isdir(dirs.saveDir+d)]
        if len(self.saveDirList) == 0:
            os.makedirs(dirs.saveDir+"Tiange")
            self.saveDirList = [d.upper() for d in os.listdir(dirs.saveDir) if os.path.isdir(dirs.saveDir+d)]      
    def saveButtonOptions(self,inputs):
        self.grabSaveList()
        ready = 0
        if inputs == "**new**save**&!@":
            if not re.match("^[a-z]*$", self.newSaveEntry.get().strip().lower()) or len(self.newSaveEntry.get().strip()) == 0:
                tkmb.showinfo("Error!", "Please only use letters [A-Z] for save names.")
            elif self.newSaveEntry.get().upper().strip() in self.saveDirList:
                tkmb.showinfo("Error!", "You cannot use an existing Save Entry Name; select it from the top dialogue instead.")
            elif len(self.newSaveEntry.get().upper().strip()) > 20:
                tkmb.showinfo("Error!", "Please stay under 20 characters.")
            else:
                ready = 1
                self.saveDirToUse = str(self.newSaveEntry.get().strip()).capitalize()
                menu = self.saveDirListMenu.children["menu"]
                menu.add_command(label=self.saveDirToUse.upper(),
                    command = lambda Dir=self.saveDirToUse.upper(): self.saveButtonOptions(Dir))
                self.dirChosen.set(self.saveDirToUse)
        else:
            ready = 1
            self.dirChosen.set(inputs)
            self.saveDirToUse = str(self.dirChosen.get()).upper()
        if ready == 1:
            preresultsDir = str(dirs.saveDir)+self.saveDirToUse+"/"+getDay(2)+"/"
            dirs.resultsDir = preresultsDir+"Session started at ["+getDay(3)+"]/" 
            os.makedirs(dirs.resultsDir)
            self.saveFileName.set("\nCurrently Selected:\n["+self.saveDirToUse.upper()+"]")
            dirs.readWriteSettings("saveName","write",str(self.saveDirToUse.upper()))
    def ljConfig(self):
        config = tk.Toplevel(self.master)
        configRun = labJackGUI(config)
        configRun.setup()
        channels,freq = dirs.readWriteSettings("labJack","read")
        self.ljString.set("Channels:\n{}\n\nScan Freq: [{}Hz]".format(channels,freq))
    def ljTest(self):
        while True:
            try:
                temp = u6.U6()
                temp.close()
                time.sleep(0.5)
                temp = u6.U6()
                temp.hardReset()
                tkmb.showinfo("Success!", "The LabJack has been properly configured")
                break
            except:
                try:
                    temp = u6.U6()
                    temp.hardReset()
                except:
                    retry = tkmb.askretrycancel("Error!",
                        "The LabJack is either unplugged or is malfunctioning.\n\nDisconnect and reconnect the device, then click Retry.")
                    if retry:
                        time.sleep(3)
                    else:
                        break
            time.sleep(0.001)






root = tk.Tk()
k=masterGUI(root)
root.mainloop()



"""
startGUI = startGUI()
startGUI.initialize()
startGUI.run()

if startGUI.guiOption == "p":
    photometryGUI = photometryGUI(dirs.prgmDir+"settings.txt")
    photometryGUI.initialize()
    photometryGUI.run()

saveLocationGUI=saveLocationGUI()
saveLocationGUI.initialize()
saveLocationGUI.run()

arduino = arduino()
labJackGUI = labJackGUI()
labJackGUI.setup()

"""


