import Tkinter as tk
import tkMessageBox as tkmb
import serial, time, ast, os, sys, platform, glob, threading, thread, copy
import calendar, traceback, re, math, Queue, struct, tkFont
from struct import *
from operator import itemgetter
from datetime import datetime
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
        usrMsg.set("\nPrevious Settings Loaded\nThese settings will be saved in your .csv outputs for use with [photometryAnalysis.py]\n")
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
        frequencyFrame = tk.LabelFrame(self.root, text="Main & Isos Frequencies")
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
        (self.descrip,self.packet,
            self.tone_pack,self.out_pack,
            self.pwm_pack) = dirs.readWriteSettings("arduino","read")
        [self.packet, self.tone_pack, 
        self.out_pack, self.pwm_pack] = [ast.literal_eval(self.packet), 
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
#Misc. Options
def printDigits(num,places,front=True,placeHolder=" "):
    if front:
        return placeHolder*(places-len(str(num)))+str(num)
    elif not front:
        return str(num)+placeHolder*(places-len(str(num)))
def printMinFromSec(secs):
    sec = secs%60
    mins = secs//60
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
                f.write("3 minutes; tone from 2:00-2:30 @ 2800hz; shock from 2:28-2:30 (connect shocker to pin 2).\n")
                f.write("['<BBLHHH', 255, 255, 180000, 1, 2, 0]\n")
                f.write("[['<LLH', 120000, 150000, 2800]]\n")
                f.write("[['<LB', 148000, 4], ['<LB', 150000, 4]]\n")
                f.write("[]\n")
                f.write("Tiange\n")
        if not os.path.exists(self.presetDir):
            os.makedirs(self.presetDir)
            #Create default examples
            f = open(self.presetDir+"example.txt","w")
            f.write("3 minutes; tone from 2:00-2:30 @ 2800hz; shock from 2:28-2:30 (connect shocker to pin 2).\n")
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
            lines = [5,6,7,8,9]
        elif typeRequired == "saveName":
            lines = [10]
        if readWrite == "read":
            hold = []
            with open(self.prgmDir+"settings.txt","r") as f:
                for i in range(11):
                    hold.append(f.readline().strip())
            return hold[lines[0]:lines[-1]+1]
        if readWrite == "write":
            with open(self.prgmDir+"settings.txt","r") as f:
                hold = []
                for i in range(11):
                    hold.append(f.readline())
            for i in range(len(lines)):
                hold[lines[i]] = args[i].strip()+"\n"
            with open(self.prgmDir+"settings.txt","w") as f:
                for i in range(11):
                    f.write(hold[i])



#####
#Arduino Related


#####
#Labjack related


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
        self.mainWindowSize = (1200,700)
        self.singleWidgetDim = 100
        self.master = master
        self.master.title("Fear Control")
        self.master.resizable(width=False, height=False)
        self.timeLabelFont = tkFont.Font(family="Helvetica", size=9)
        #########################################
        #Give each setup GUI its own box
        ####
    #photometry config
        #frame
        photometryFrame = tk.LabelFrame(self.master,
            text="Optional Photometry Config.",
            width = self.singleWidgetDim*2, height = self.singleWidgetDim)
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
            width = self.singleWidgetDim*2, height = self.singleWidgetDim)
        saveFileFrame.grid(row=0, column=1, columnspan=1,sticky=tk.W+tk.E+tk.N+tk.S)
        #display save name chosen
        self.saveFileName = tk.StringVar()

        saveFileLabel = tk.Label(saveFileFrame,textvariable=self.saveFileName,relief=tk.RAISED)
        saveFileLabel.pack(side=tk.TOP,expand="yes",fill="both")
        #secondary save frames: /existing saves
        existingSaveFrame = tk.LabelFrame(saveFileFrame, text="Select a Save Name")
        existingSaveFrame.pack(fill="both", expand="yes")
        self.dirChosen = tk.StringVar()
        lastUsed = dirs.readWriteSettings("saveName","read")[0]
        self.saveFileName.set("\nMost Recent Save Dir.:\n[{}]".format(lastUsed))
        self.dirChosen.set("{: <25}".format(lastUsed.upper()))        
        self.saveDirListMenu = tk.OptionMenu(existingSaveFrame,self.dirChosen,*self.saveDirList,command=self.saveButtonOptions)
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
            width=self.singleWidgetDim*2, height = self.singleWidgetDim)
        ljFrame.grid(row=0,column=2,sticky=tk.W+tk.E+tk.N+tk.S)
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
        ardBackgroundHeight = 260
        ardFrame = tk.LabelFrame(self.master,
            text = "Arduino Stimuli Config.",
            width = self.singleWidgetDim*11,height = ardBackgroundHeight)
        ardFrame.grid(row=10,column=0,columnspan=99,sticky=tk.W+tk.E+tk.N+tk.S)
        ardCanvas = tk.Canvas(ardFrame, width = 1000+10, height = ardBackgroundHeight+10)
        ardCanvas.pack()
        ardCanvas.create_rectangle(0,0, 1000, 
            ardBackgroundHeight, fill="black",outline="black")
        ardCanvas.create_rectangle(0,30-1, 1000, 30+1, fill="white")
        ardCanvas.create_rectangle(0,150-1, 1000, 150+1, fill="white")
        #grab last used data
        #(descrip,packet,tone_pack,out_pack,pwm_pack)
        self.ardData = arduinoGUI(tk.Toplevel())
        self.ardData.root.quit()
        self.ardData.root.destroy()
        divisor = 5+5*int(self.ardData.packet[3]/300000)
        segment = float(self.ardData.packet[3]/1000)/divisor
        for i in range(int(round(segment))):
            if i > 0:
                ardCanvas.create_rectangle(i*(1000.0/segment)-1,0, i*(1000.0/segment)+1, 
                    ardBackgroundHeight, fill="white")
                if i%2 == 0:
                    ardCanvas.create_text(i*(1000.0/segment),ardBackgroundHeight+8,
                        text=printMinFromSec(divisor*i),fill="black",font=self.timeLabelFont)
        toneData, outData, pwmData = -1, -1, -1
        if len(self.ardData.tone_pack) != 0:
            toneData = self.decodeArdData("tone",self.ardData.tone_pack)
            for i in toneData:
                ardCanvas.create_rectangle(i[0],0+10, i[1]+i[0], 30, fill="yellow")
                ardCanvas.create_text(i[0]+2,11,text="{} Hz".format(i[3]), 
                    fill="black", anchor = tk.NW)
        if len(self.ardData.out_pack) != 0:
            pinIDs = [2,3,4,5,6,7]
            outData = self.decodeArdData("output",self.ardData.out_pack)
            for i in range(len(outData)):
                yPosition = 30+(pinIDs.index(outData[i][3]))*20
                ardCanvas.create_rectangle(outData[i][0],yPosition, 
                    outData[i][1]+outData[i][0], yPosition+20, fill="yellow")
        if len(self.ardData.pwm_pack) != 0:
            pinIDs = [8,9,11,12,13]
            pwmData = self.decodeArdData("pwm",self.ardData.pwm_pack)
            for i in range(len(pwmData)):
                yPosition = 150+(pinIDs.index(pwmData[i][3]))*20
                ardCanvas.create_rectangle(pwmData[i][0],yPosition, 
                    pwmData[i][1]+pwmData[i][0], yPosition+20, fill="yellow")







            
            
        ####
    #update window
        self.updateWindow()
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
                ardData.append([startSpace,onSpace,offSpace,i[3]])
            elif name == "pwm":
                ardData.append([startSpace,onSpace,offSpace,
                    checkBin(i[5],"B")[0],i[4],i[7],i[6]])
            elif name == "output":
                ardData.append([startSpace,onSpace,offSpace,i[0]])
        return ardData
    def updateWindow(self):
        self.master.update_idletasks()
        w = self.master.winfo_screenwidth()
        h = self.master.winfo_screenheight()
        size = self.mainWindowSize
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
                    tkmb.showinfo("Error!", 
                        "The LabJack is either unplugged or is malfunctioning.\n\nDisconnect and reconnect, then click OK to try again.")
                    time.sleep(3)
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


