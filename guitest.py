import Tkinter as tk
import tkMessageBox as tkmb
import os, copy

class startGUI():
	def __init__(self):
		#call gui
		self.root = tk.Tk()
		self.root.title("Fear Control")
		#initialize some button options
		innerFrame = tk.LabelFrame(self.root, text="Select an option to Begin")
		beginButton = tk.Button(innerFrame, text = "NORMAL", command = lambda: self.buttonBegin("normal"))
		photoButton = tk.Button(innerFrame, text = "PHOTOMETRY", command = lambda: self.buttonBegin("photo"))
		beginButton.pack(side=tk.BOTTOM)
		photoButton.pack(side=tk.BOTTOM)
		innerFrame.pack(fill="both", expand="yes")
		#open window in middle of screen
		windowWidth = self.root.winfo_screenwidth()
		windowHeight = self.root.winfo_screenheight()
		rootWidth = 350
		rootHeight = 80
		x = (windowWidth/2)-(rootWidth/2)
		y = (windowHeight/2)-(rootHeight/2)
		self.root.geometry("%dx%d+%d+%d" % (rootWidth,rootHeight,x,y))
		#open GUI
		self.root.mainloop()
	def buttonBegin(self,var):
		self.root.destroy()
		if var == "normal":
			self.guiOption = ""
		if var == "photo":
			self.guiOption = "p"
class photometryGUI():
	def __init__(self):
		#call gui
		self.root = tk.Tk()
		self.root.title("Fear Control - Photometry Options")
		self.trueDataCh, self.trueRefCh, self.isosDataCh, self.isosRefCh = 0,0,0,0
		#variables to hold input
		(trueData, trueRef, isosData, isosRef, 
			trueRefFreq, isosRefFreq) = (tk.IntVar(), tk.IntVar(), 
			tk.IntVar(), tk.IntVar(), 
			tk.IntVar(), tk.IntVar())
		dataButtons = [trueData, trueRef, isosData, isosRef]
		dataFields = [trueRefFreq, isosRefFreq]
		#initialize frames
		trueDataFrame = tk.LabelFrame(self.root, text="Main Photometry Channel")
		trueRefFrame = tk.LabelFrame(self.root, text="Main Reference Channel")
		isosDataFrame = tk.LabelFrame(self.root, text="Isosbestic Channel")
		isosRefFrame = tk.LabelFrame(self.root, text="Isosbestic Reference Channel")
		dataFrames = [trueDataFrame, trueRefFrame, isosDataFrame, isosRefFrame]
		#initialize container boxes:
		for frame in range(len(dataFrames)):
			dataFrames[frame].pack(fill="both",expand="yes")
			for i in range(14):
				R = tk.Radiobutton(dataFrames[frame],text=str(i),
					variable=dataButtons[frame],
					value = i, command=lambda: self.selectButton(dataButtons[frame],frame))
				R.pack(side=tk.LEFT)
		frequencyFrame = tk.LabelFrame(self.root, text="Main & Isos Frequencies")
		frequencyFrame.pack(fill="both",expand="yes")
		L1 = tk.Label(frequencyFrame,text="Main Frequency: ")
		L1.pack(side=tk.LEFT)
		E1 = tk.Entry(frequencyFrame)
		E1.pack(side=tk.LEFT)
		L2 = tk.Label(frequencyFrame,text="Isosbestic Frequency: ")
		L2.pack(side=tk.LEFT)
		E2 = tk.Entry(frequencyFrame)
		E2.pack(side=tk.LEFT)
		#button to exit
		doneButton = tk.Button(self.root,text="Finish",command = self.exitButton)
		doneButton.pack(side=tk.BOTTOM)
		#open window in middle of screen
		windowWidth = self.root.winfo_screenwidth()
		windowHeight = self.root.winfo_screenheight()
		rootWidth = 500
		rootHeight = 400
		x = (windowWidth/2)-(rootWidth/2)
		y = (windowHeight/2)-(rootHeight/2)
		self.root.geometry("%dx%d+%d+%d" % (rootWidth,rootHeight,x,y))
		self.root.mainloop()
	def selectButton(self,var,i):
		channelSelected = [self.trueDataCh, self.trueRefCh, self.isosDataCh, self.isosRefCh]
		self.trueDataCh = var.get()
		print self.trueDataCh, self.trueRefCh, self.isosDataCh, self.isosRefCh
	def exitButton(self):
		self.root.destroy()











##############################################################################################################
#=================================================PROGRAM====================================================#
##############################################################################################################
userhome = os.path.expanduser('~')
baseDir = userhome+"/desktop/arduinoControl/"
presetDir = baseDir+"UserPresets/"
prgmDir = baseDir+"prgmSettings/"
saveDir = baseDir+"outputSaves/"
####################
#CHECKING FOR DIRECTORIES
if not os.path.exists(prgmDir):
	os.makedirs(prgmDir)
	#Create default examples
	with open(prgmDir+"example preset.txt","w") as f:
		f.write("[0,1,2,3]\n")
		f.write("5000\n")
if not os.path.isfile(prgmDir+"settings.txt"):
	#Just in case settings.txt is deleted but not prgmDir:
	#we will make settings.txt anyway
	with open(prgmDir+"settings.txt","w") as f:
		f.write("/dev/cu.usbmodem1421\n")
		f.write("[0,2]\n")
		f.write("20000\n")
		f.write("N/A1\n")
		f.write("N/A2\n")
if startGUI().guiOption == "p":
	k = photometryGUI()
	print k.trueDataCh, k.trueRefCh, k.isosDataCh, k.isosRefCh