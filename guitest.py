import Tkinter as tk
import tkMessageBox as tkmb
import serial, time, ast, os, sys, platform, glob, threading, thread, copy
import calendar, traceback, re #LabJackPython, math, Queue, struct #u6,
from struct import *
#from u6 import U6
from operator import itemgetter
from datetime import datetime
#import numpy as np
#import flycapture2a as fc2

#####
#GUIs
class GUI():
    def __init__(self):
        self.root = tk.Tk()
        self.root.title(self.title)
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
class startGUI(GUI):
    def __init__(self):
        self.title = "Fear Control"
        GUI.__init__(self)
    def initialize(self):
        innerFrame = tk.LabelFrame(self.root, text="Select an option to Begin")
        beginButton = tk.Button(innerFrame, text = "NORMAL", command= lambda:self.buttonOptions("normal"))
        photoButton = tk.Button(innerFrame, text = "PHOTOMETRY", command= lambda:self.buttonOptions("photometry"))
        beginButton.pack(side=tk.BOTTOM)
        photoButton.pack(side=tk.BOTTOM)
        innerFrame.pack(fill="both", expand="yes")
    def buttonOptions(self,choice):
        self.root.destroy()
        if choice == "normal":
            self.guiOption = ""
        elif choice == "photometry":
            self.guiOption = "p"
class photometryGUI(GUI):
    def __init__(self,file):
        self.title = "Photometry Options"
        GUI.__init__(self)
        with open(file,"r") as f:
            self.sLine1, self.sLine2, self.sLine3 = f.readline(), f.readline(), f.readline()
            self.photometryConfig1, self.photometryConfig2 = ast.literal_eval(f.readline().strip()), ast.literal_eval(f.readline().strip())
            self.trueDataCh, self.trueRefCh, self.isosDataCh, self.isosRefCh = map(int,self.photometryConfig1)
            self.trueDataFreq, self.isosDataFreq = map(int,self.photometryConfig2)    
    def initialize(self):
        #variables to hold input
        (trueData, trueRef, isosData, isosRef, 
            trueRefFreq, isosRefFreq) = (tk.IntVar(), tk.IntVar(), 
            tk.IntVar(), tk.IntVar(), 
            tk.IntVar(), tk.IntVar())
        #Initialize button variables from file:
        self.dataButtons = [trueData, trueRef, isosData, isosRef]
        for i in range(len(self.dataButtons)):
            self.dataButtons[i].set(self.photometryConfig1[i])
        #initialize frames for buttons
        usrMsg = tk.StringVar()
        label = tk.Label(self.root, textvariable = usrMsg, relief = tk.RAISED)
        usrMsg.set("\nPrevious Settings Loaded\nThese settings will be saved in your .csv outputs for use with [photometryAnalysis.py]\n")
        label.pack(fill="both",expand="yes")
        trueDataFrame = tk.LabelFrame(self.root, text="Main Photometry Channel")
        trueRefFrame = tk.LabelFrame(self.root, text="Main Reference Channel")
        isosDataFrame = tk.LabelFrame(self.root, text="Isosbestic Channel")
        isosRefFrame = tk.LabelFrame(self.root, text="Isosbestic Reference Channel")
        dataFrames = [trueDataFrame, trueRefFrame, isosDataFrame, isosRefFrame]
        #initialize container boxes for buttons
        R = [[[]]*14]*len(dataFrames)
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
        self.channelSelected = [self.trueDataCh, self.trueRefCh, self.isosDataCh, self.isosRefCh]
        if var.get() not in self.channelSelected:
            self.channelSelected[i] = var.get()
        else:
            tempChReport = ["Main Photometry Channel","Main Reference Channel","Isosbestic Channel","Isosbestic Reference Channel"]
            tempChReport = tempChReport[self.channelSelected.index(var.get())]
            tkmb.showinfo("Error!", "You already selected [Channel {}] for [{}]!".format(var.get(),tempChReport))
            self.dataButtons[i].set(self.photometryConfig1[i])
        [self.trueDataCh, self.trueRefCh, self.isosDataCh, self.isosRefCh] = self.channelSelected
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
                with open(dirs.prgmDir+"settings.txt","w") as f:
                    f.write(self.sLine1)
                    f.write(self.sLine2)
                    f.write(self.sLine3)
                    f.write(str(self.photometryConfig1)+"\n")
                    f.write(str(self.photometryConfig2)+"\n")
        except ValueError:
            tkmb.showinfo("Error!", "You must enter integer options into both frequency fields.")
class saveLocationGUI(GUI):
    def __init__(self):
        self.title = "Choose a Save Location"
        GUI.__init__(self)
        self.saveDirList = [d.upper() for d in os.listdir(dirs.saveDir) if os.path.isdir(dirs.saveDir+d)]
        if len(self.saveDirList) == 0:
            os.makedirs(dirs.saveDir+"Tiange")
            self.saveDirList = [d.upper() for d in os.listdir(dirs.saveDir) if os.path.isdir(dirs.saveDir+d)]
    def initialize(self):
        #existing directories
        existingFrame = tk.LabelFrame(self.root, text="Select a Save Name")
        existingFrame.pack(fill="both", expand="yes")
        self.dirChosen = tk.StringVar()
        self.dirChosen.set(max(self.saveDirList, key=len))
        saveDirList = apply(tk.OptionMenu, (existingFrame, self.dirChosen)+tuple(self.saveDirList))
        saveDirList.pack(side=tk.LEFT)
        selectButton = tk.Button(existingFrame, text = "Confirm", command=lambda:self.buttonOptions("existing"))
        selectButton.pack(side = tk.RIGHT)
        #create a new directory
        newSaveFrame = tk.LabelFrame(self.root, text="Create a New Save Name")
        newSaveFrame.pack(fill="both", expand="yes")
        self.newSaveEntry = tk.Entry(newSaveFrame)
        self.newSaveEntry.pack(side=tk.TOP)
        newSaveButton = tk.Button(newSaveFrame, text = "Create New", command=lambda:self.buttonOptions("new"))
        newSaveButton.pack(side = tk.TOP)
    def buttonOptions(self,choice):
        ready = 0
        if choice == "existing":
            ready = 1
            dirToUse = str(self.dirChosen.get()).capitalize()
        elif choice == "new":
            if not re.match("^[a-z]*$", self.newSaveEntry.get().strip().lower()) or len(self.newSaveEntry.get().strip()) == 0:
                tkmb.showinfo("Error!", "Please only use letters [A-Z] for save names.")
            elif self.newSaveEntry.get().upper().strip() in self.saveDirList:
                tkmb.showinfo("Error!", "You cannot use an existing Save Entry Name; select it from the top dialogue instead.")
            else:
                ready = 1
                dirToUse = str(self.newSaveEntry.get().strip()).capitalize()
        if ready == 1:
            preresultsDir = str(dirs.saveDir)+dirToUse+"/"+getDay(2)+"/"
            dirs.resultsDir = preresultsDir+"Session started at ["+getDay(3)+"]/" 
            os.makedirs(dirs.resultsDir)
            self.root.destroy()
class labJackGUI(GUI):
    def __init__(self):
        self.MAX_REQUESTS, self.SMALL_REQUEST = 0, 0
        self.stlFctr, self.ResIndx = 1, 0
        self.ljSaveName = ""
        with open(dirs.prgmDir+"settings.txt","r") as f:
            f.readline()
            self.chNum = ast.literal_eval(f.readline())
            self.scanFreq = int(f.readline())
            self.nCh, self.chOpt = len(self.chNum), [0]*len(self.chNum)
        self.title = "LabJack Options"
        GUI.__init__(self)
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
        savePresetList = tk.OptionMenu(existingFrame,self.presetChosen,*self.presetSaveList,command=self.listChoose)
        savePresetList.pack(side=tk.TOP)
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
                elif os.path.isfile(dirs.prgmDir+saveName+".txt"):
                    if tkmb.askyesno("Overwrite", "[{}] already exists.\nOverwrite this preset?".format(saveName.upper())):
                        with open(dirs.prgmDir+saveName+".txt","w") as f:
                            f.write(str(self.chNum)+"\n"+str(self.scanFreq)+"\n")
                            tkmb.showinfo("Saved!", "Preset saved as [{}]".format(saveName.upper()))
    def exitButton(self):
        validity = self.checkInputValidity()
        if validity == 1:
            self.root.destroy()
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
                with open(dirs.prgmDir+"settings.txt","r") as f:
                    hold = []
                    for i in range(5):
                        hold.append(f.readline())
                with open(dirs.prgmDir+"settings.txt","w") as f:
                    f.write(hold[0])
                    f.write(str(self.chNum)+"\n")
                    f.write(str(self.scanFreq)+"\n")
                    f.write(hold[3])
                    f.write(hold[4])
        except ValueError:
            tkmb.showinfo("Error!", "Scan Frequency must be an integer in Hz.")
        return validity
    def listChoose(self,fileName):
        with open(dirs.prgmDir+fileName+".txt") as f:
            self.chNum = map(int,ast.literal_eval(f.readline().strip()))
            self.scanFreq = int(f.readline().strip())
            print self.chNum, self.scanFreq
            for i in range(14):
                self.buttonVars[i].set(0)
            for i in self.chNum:
                self.buttonVars[i].set(1)
            self.nCh, self.chOpt = len(self.chNum), [0]*len(self.chNum)
            self.E1.delete(0,"end")
            self.E1.insert(tk.END,self.scanFreq) 

#####
#Misc. Options
def printDigits(num,places,front=True,placeHolder=" "):
    if front:
        return placeHolder*(places-len(str(num)))+str(num)
    elif not front:
        return str(num)+placeHolder*(places-len(str(num)))
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
                f.write("/dev/cu.usbmodem1421\n")
                f.write("[0,2]\n")
                f.write("20000\n")
                f.write("[0,1,2,3]\n")
                f.write("[0,0]\n")
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

#####
#Arduino Related
class arduino():
    def __init__(self):
        with open(dirs.prgmDir+"settings.txt","r") as f:
            self.serPort = f.readline().strip()

#####
#Labjack related
"""
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
    def tryStartLJ(self):
        try:
            temp = u6.U6()
            temp.close()
            return "success"
        except:
            return "failed"
"""




#####
#Camera Related



cameraSaveName = ""



##############################################################################################################
#=================================================PROGRAM====================================================#
##############################################################################################################
dirs = dirs()
dirs.setupMainDirs()











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




