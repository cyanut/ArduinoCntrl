####################
#TIME OUT DECORATORS
def cdquit(fn_name):
	sys.stderr.flush()
	thread.interrupt_main()
def exit_after(s):
	def outer(fn):
		def inner(*args,**kwargs):
			timer = threading.Timer(s, cdquit, args=[fn.__name__])
			timer.start()
			try:
				result = fn(*args,**kwargs)
			finally:
				timer.cancel()
			return result
		return inner
	return outer
####################

####################
#ARDUINO COMMUNICATIONS
def sendToArduino(sendStr):
	ser.write(sendStr)
def recvFromArduino():
	global startMarker, endMarker
	ck = ""
	x = "z"
	byteCount = -1
	while ord(x) != startMarker:
		x = ser.read()
	while ord(x) != endMarker:
		if ord(x) != startMarker:
			ck = ck + x
			byteCount += 1
		x = ser.read()
	return(ck)
@exit_after(10)
def waitForArduino():
	global startMarker, endMarker
	msg = ""
	print "Attempting to communicate with Arduino..."
	i = 0
	while msg.find("Arduino is ready") == -1:
		while ser.inWaiting() == 0:
			time.sleep(0.1)
			if (i+1)%10==0 and ((i+1)<30 or (i+1)>30):
				sys.stdout.write("\rWaiting.."+"."*(i/10))
			if i+1 == 30:
				sys.stdout.write("\rArduino is taking longer than usual to connect...\nWaiting.....")
			sys.stdout.flush()
			i += 1
		msg = recvFromArduino()
	print "\n\nArduino connection Established! Sending data packets..."
def sendPackets(*args):
	for each in args:
		for i in range(len(each)):
			if len(each)>0:
				retStr = recvFromArduino()
				if retStr == "M":
					sendToArduino(pack(*each[i]))
def startSerial():
	global ser, serPort, baudRate, mainLoopbrk, num_loops, reset
	serialbrkMain = 0
	while serialbrkMain == 0:
		try:
			if num_loops == 0 or reset != 0:
				ser = serial.Serial(serPort,baudRate)
			elif num_loops > 0:
				ser.setDTR(False) 
				time.sleep(0.022)
				ser.setDTR(True)
			print gfxBar(40)
			print "OPENED: Port [" + serPort + "] @ Baudrate [" + str(baudRate) + "]"
			try:
				waitForArduino()
				reset = 0
				break
			except IOError:
				print "\n"*4+"Serial Port [%s] is either occupied or cannot be opened." %serPort
				reset = 1
			except KeyboardInterrupt:
				print "\n\n\n\nArduino is taking too long to respond."
				print "Serial Port has been [RESET]. Please select a new one."
				raw_input("Press [enter] to continue: ")
				print "\n"*2
				serPort, reset = "[resetPortReset]", 1
		except (serial.SerialException, IOError):
			print "\n"*4+"Serial Port [%s] is either occupied or cannot be opened." %serPort
			reset = 1
		serialPorts = list_serial_ports()
		serialPortsMsg = "\n".join(str(i)+" - ["+serialPorts[i]+"]" for i in range(len(serialPorts)))
		print gfxBar(0,1,"LIST OF AVAILABLE SERIAL PORTS:\n\n"+serialPortsMsg)
		serialbrkOptions = 0
		while serialbrkOptions == 0:
			if serPort != "[resetPortReset]":
				print "[Y] - Try Port [%s] Again" % serPort
			print "[N] - Exit This Program Session"
			print str([i for i in range(len(serialPorts))]) + " - Select a different Serial Port."
			ask_exit = raw_input("Select an option from above: ").lower()
			ask_exitErrorMsg = "\nType [Y/N] or "+str([i for i in range(len(serialPorts))])+" to Continue"
			try:
				ask_exit = int(ask_exit)
				if ask_exit in range(len(serialPorts)):
					serPort = serialPorts[ask_exit]
					f = open(prgmDir+"settings.txt","r")
					temp = []
					for i in range(5):
						temp.append(f.readline())
					f.close()
					f = open(prgmDir+"settings.txt","w")
					f.write(serialPorts[ask_exit]+"\n")
					for i in range(4):
						f.write(temp[i+1])
					f.close()
					print "\n\nTrying New Serial Port [%s]" % serPort
					break
				else:
					if serPort == "[resetPortReset]":
						print ask_exitErrorMsg[:7]+ask_exitErrorMsg[9:]
					else:
						print ask_exitErrorMsg
			except ValueError:
				if ask_exit == "y" and serPort != "[resetPortReset]":
					print "\n\nTrying Serial Port[%s] Again..." % serPort
					break
				elif ask_exit == "n":
					print "\n"*40+"Exiting Program...\nFinished."
					mainLoopbrk = 1
					serialbrkMain = 1
					break
				else:
					if serPort == "[resetPortReset]":
						print ask_exitErrorMsg[:7]+ask_exitErrorMsg[9:]
					else:
						print ask_exitErrorMsg
####################

####################
#MISC FUNCTIONS
def posToInt(a):
	if a < 8:
		return (int("1"+"0"*int(a),2))
	if a >= 8 and a <= 13:
		return (int("1"+"0"*(int(a)-8),2))
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

def list_serial_ports():
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
def consoleResize(x,y):
	if sys.platform.startswith('win'):
		os.system("mode con: cols=%s lines=%s"%(x, y)) 
	elif sys.platform.startswith('linux') or sys.platform.startswith('cygwin'):
		sys.stdout.write("\x1b[8;{rows};{cols}t".format(rows=y, cols=x))
		sys.stdout.flush()
	elif sys.platform.startswith('darwin'):
		sys.stdout.write("\x1b[8;{rows};{cols}t".format(rows=y, cols=x))
		sys.stdout.flush()
	else:
		raise EnvironmentError('Unsupported platform')
def dictFlatten(*args):
	hold = []
	for a in args:
		hold.append([i for s in a.values() for i in s])
	return hold
def fileMultiRead(file_name,*args):
	global presetDir
	f = open(presetDir+file_name+".txt")
	hold = []
	for i in args:
		if i == 0:
			f.readline()
		else:
			hold.append(ast.literal_eval(f.readline()))
	f.close()
	return hold
def fileMultiWrite(file_name,*args):
	global presetDir
	f = open(presetDir+file_name+".txt","w")
	for i in args:
		f.write(str(i)+"\n")
	f.close()

####################

####################
#IMAGE ELEMENTS
def gfxBar(upperClearance=0,lowerClearance=0,msg=0):
	if msg == 0:
		return "\n"*upperClearance+"#"*65+"\n"*lowerClearance
	else:
		return "\n"*upperClearance+"#"*65+"\n"+msg+"\n"+"#"*65+"\n"*lowerClearance
def gfxWord(types):
	if types == "tone":
		print "_________ _______  _        _______  _______ "
		print "\__   __/(  ___  )( (    /|(  ____ \(  ____ \\"
		print "   ) (   | (   ) ||  \  ( || (    \/| (    \/"
		print "   | |   | |   | ||   \ | || (__    | (_____ "
		print "   | |   | |   | || (\ \) ||  __)   (_____  )"
		print "   | |   | |   | || | \   || (            ) |"
		print "   | |   | (___) || )  \  || (____/\/\____) |"
		print "   )_(   (_______)|/    )_)(_______/\_______)"
	elif types == "output":
		print " _______          _________ _______          _________"
		print "(  ___  )|\     /|\__   __/(  ____ )|\     /|\__   __/"
		print "| (   ) || )   ( |   ) (   | (    )|| )   ( |   ) (   "
		print "| |   | || |   | |   | |   | (____)|| |   | |   | |   "
		print "| |   | || |   | |   | |   |  _____)| |   | |   | |   "
		print "| |   | || |   | |   | |   | (      | |   | |   | |   "
		print "| (___) || (___) |   | |   | )      | (___) |   | |   "
		print "(_______)(_______)   )_(   |/       (_______)   )_(   "
	elif types == "pwm":
		print " _______           _______ "
		print "(  ____ )|\     /|(       )"
		print "| (    )|| )   ( || () () |"
		print "| (____)|| | _ | || || || |"
		print "|  _____)| |( )| || |(_)| |"
		print "| (      | || || || |   | |"
		print "| )      | () () || )   ( |"
		print "|/       (_______)|/     \|"
def gfxFormat(types,sep):
	on, off, pin, freq, duty, phase = "SECONDS_UNTIL_ON","SECONDS_ON_FOR","PIN_USED","FREQUENCY_HZ","DUTY_CYCLE(%)", "PHASE_SHIFT"
	msg = on+sep+off+sep
	if types == "tone":
		msg = msg+freq
	elif types == "output":
		msg = msg+pin
	elif types == "pwm":
		msg = msg+freq+sep+pin+sep+duty+sep+phase
	if sep == " | ":
		msg = sep+msg+sep
	return msg
def gfxSetup(types):
	print gfxBar(40)
	gfxWord(types)
	print gfxBar(0,0,"[INPUT FORMAT]: "+gfxFormat(types,", "))
	if types == "tone":
		print ">>>USE FOR FREQUENCIES [>50HZ].\n"
	if types == "output":
		print ">>>USE PINS 2-7 (INCLUSIVE).\n"
	if types == "pwm":
		print ">>>USE PINS 8-13 (INCLUSIVE, EXCEPT 10)."
		print ">>>USE FOR FREQUENCIES [<100HZ].\n"
def gfxTimeDisplay(name,dataSource,timeSegment):
	print " "*101+">"+name.upper()+":"
	if name == "tones":
		start, on = 1, 2
	elif name == "frequency modulated outputs":
		start, on = 2, 3
	elif name == "simple outputs":
		indivTriggers, indivTimes, triggerTimes, finalInterval = [], [], {}, []
		start, on = 1, 2
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
	for i in dataSource:
		startSpace = int(round((float(i[start])/timeSegment)))
		onSpace = int(round(float(i[on])/timeSegment))-startSpace
		if onSpace == 0:
			startSpace = startSpace - 1
			onSpace = 1
		offSpace = 100-onSpace-startSpace
		bar = " "*startSpace+"-"*onSpace+" "*offSpace
		if name == "tones":
			print bar+" ["+printDigits(i[1]/1000,3)+"s - "+printDigits(i[2]/1000,3)+"s][10]["+printDigits(i[3],4)+" Hz]"
		elif name == "simple outputs":
			print bar+" ["+printDigits(i[1]/1000,3)+"s - "+printDigits(i[2]/1000,3)+"s]["+printDigits(i[0],2)+"][  n/a  ]"
		elif name == "frequency modulated outputs":
			print bar+" ["+printDigits(i[2]/1000,3)+"s - "+printDigits(i[3]/1000,3)+"s]["+printDigits(checkBin(i[5],"B")[0],2)+"]["+printDigits(i[4],4)+" Hz-"+printDigits(i[7],2)+"%-"+printDigits(i[6],3)+" deg]"
####################

####################
#GET USER INPUTS
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
####################

####################
#TURN USER INPUTS INTO DATA PACKETS
def retrieveSettings(ask_file, allFiles):
	global presetDir, packet, tone_pack, out_pack, pwm_pack
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
def run_setup(settings):
	global packet,tone_pack,out_pack,pwm_pack,total_time,serPort,baudRate,ser,mainLoopbrk,expName
	if settings == "enter_new":
		setupMainLoop = 0
		while setupMainLoop == 0:
			packet = ["<BBLHHH",255,255,0,0,0,0]
			tone_pack, out_pack, pwm_pack, total_time = [],[],[],0
			Loop1 = 0
			while Loop1 == 0:
				allFiles = []
				if os.path.exists(presetDir):
					for f in os.listdir(presetDir):
						if f.endswith(".txt"):
							allFiles.append(f)
					if len(allFiles) == 0:
						ask_file = "n"
					elif len(allFiles) > 0:
						print gfxBar(40,1,">>>EXPERIMENT SETUP")
						ask_file = raw_input("\nUse Saved Experiment Settings? (Y/N): ").lower()
				else:
					os.makedirs(presetDir)
					ask_file = "n"
				Loop1 = retrieveSettings(ask_file,allFiles)
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
def runExperiment():
	global packet, tone_pack, out_pack, pwm_pack, num_loops, mainLoopbrk, reset, resultsDir, ljSaveName, cameraSaveName, runDone
	stopLoop = 0
	sendToArduino(pack("<B",1))
	while True:
		print "\n"*40+"#"*10
		print "The experiment has started."
		print "Arduino millisecond counter has been reset to [0ms]."
		print gfxBar()
		###
		#RUNNING TIMER
		timeSegment = float(float(packet[3])/float(100))
		print "-"*100+" [TOTAL TIME]: [" +str(packet[3]/1000) +"s]"
		print " "*101+"|  ON -  OFF|PIN|Freq-DtyCycl-PhsShft|"
		gfxTimeDisplay("tones",tone_pack,timeSegment)
		gfxTimeDisplay("simple outputs",out_pack,timeSegment)
		gfxTimeDisplay("frequency modulated outputs",pwm_pack,timeSegment)
		###
		#PROGRESS BAR HERE
		startProg = datetime.now()
		barCounter, timeCounter = 0, 0.0
		segmentSize = (float(packet[3])/1000)/100
		timeSize = 0.1
		numTime, numProg = 1, 1
		while True:
			now = datetime.now()
			timeDiff = (now-startProg).seconds+float((now-startProg).microseconds)/1000000
			if timeDiff/numTime >= timeSize:
				numTime += 1
				timeCounter += timeSize
			if timeDiff/numProg >= segmentSize:
				numProg += 1
				barCounter += 1
			if barCounter == 0:
				barCounter, timeCounter = min(barCounter,99), min(timeCounter,float(packet[3]/1000)-0.1)
				sys.stdout.write("\r"+"*"+"-"*(99-barCounter)+" ["+str(timeCounter)+"s]")
				sys.stdout.flush()
			elif barCounter in range(1,100):
				barCounter, timeCounter = min(barCounter,99), min(timeCounter,float(packet[3]/1000)-0.1)
				sys.stdout.write("\r"+"-"*(barCounter-1)+"|"+"-"*(100-barCounter)+" ["+str(timeCounter)+"s]")
				sys.stdout.flush()
			elif barCounter >= 100 and timeCounter >= float(packet[3]/1000)-timeSize:
				barCounter, timeCounter = 100, float(packet[3]/1000)
				sys.stdout.write("\r"+"-"*(barCounter-1)+"*"+" [Finished: "+str(timeCounter)+"s]")
				sys.stdout.flush()
				break
		###
		try:
			ardMsg2 = recvFromArduino()
			endMillis = ardMsg2.split(",")[0]
			startRTC = ardMsg2.split(",")[1]
			endRTC = ardMsg2.split(",")[2]
		except serial.serialutil.SerialException:
			print gfxBar(2)
			print "[ATTN]: The Arduino was disconnected during the experiment."
			raw_input("Reconnect the hardware and press [enter] to try again: ")
			stopLoop, reset = 1, 1
			num_loops += 1
			break
		print gfxBar(1)
		print "The experiment has ended."
		print "Arduino reports exactly [%s ms], from [%s] to [%s]." % (endMillis, startRTC, endRTC)
		print "#"*10
		runDone = 1
		break
	while True:
		if runDone == 2:
			break
		time.sleep(0.001)
	print "\n"*2+"[SAVE DIRECTORY]: '"+resultsDir+"'"
	print "[LABJACK DATA  ]: '"+ljSaveName+".csv'"
	print "[VIDEO OUTPUT  ]: '"+cameraSaveName+".mp4'"
	raw_input("Press [enter] to Continue")
	while True:
		userPlot = raw_input("\nGraph your Data? (Y/N): ").lower()
		if userPlot == "y":
			print "Your plot will appear in your system's default browser.\nThis may take a moment for long procedures..."
			plotData()
			break
		elif userPlot == "n":
			break
		else:
			print "Type (Y/N) to Continue"
	while stopLoop == 0:
		user_stop = raw_input("\nRerun experiment? (Y/N): ").lower()
		if user_stop == "y":
			num_loops += 1
			break
		elif user_stop == "n":
			mainLoopbrk = 1
			cameraClose(cameraCtx)
			print "\n"*40+"Finished."
			break
		else:
			print "Type (Y/N) to Continue"
####################

####################
#LABJACK CONFIGURATION


def startLJ(lj):
	global nCh, chNum, chOpt, stlFctr, ResIndx, scanFreq
	lj.getCalibrationData()
	lj.streamConfig(nCh,ResIndx,25,stlFctr,0,False,1,chNum,chOpt,scanFreq,None)
	return lj
class StreamDataReader(object):
    def __init__(self, device):
        self.device = device
        self.data = Queue.Queue()
        self.dataCountMain = 0
        self.dataCountAux1 = 0
        self.dataCountAux2 = 0
        self.running = False
    def readStreamData(self):
        global timeStart, packet, nCh, runDone, timeStartRead, sdrMissedList
        global sdrMissed, beforeStart, runTime, afterStop, ttlRunTime
        global sdrTotalAux1, sdrTotalAux2, sdrTotalMain, sdrTotal
        global finalSmplFreq, finalScanFreq, finalSmplFreqExp, finalScanFreqExp
        global missedBefore, missedDuring, missedAfter
        self.running = True
        self.device.streamStart()
        timeStartRead = datetime.now()
        while True:
            returnDict = self.device.streamData(convert = False).next()
            self.data.put_nowait(copy.deepcopy(returnDict))
            self.dataCountAux1 += 1
            if self.dataCountAux1 >= SMALL_REQUEST:
                break
        timeStart = datetime.now()
        while True:
            returnDict = self.device.streamData(convert = False).next()
            self.data.put_nowait(copy.deepcopy(returnDict))
            self.dataCountMain += 1
            if self.dataCountMain >= MAX_REQUESTS:
                break
        stop = datetime.now()
        while self.running:
            returnDict = self.device.streamData(convert = False).next()
            self.data.put_nowait(copy.deepcopy(returnDict))
            self.dataCountAux2 += 1
            if self.dataCountAux2 >= SMALL_REQUEST:
                self.running = False
        stopRead = datetime.now()
        self.device.streamStop()
        self.device.close()
        #Total Samples Taken for each interval
        multiplier =  self.device.packetsPerRequest * self.device.streamSamplesPerPacket
        sdrTotalAux1 = (self.dataCountAux1)*multiplier
        sdrTotalMain = (self.dataCountMain)*multiplier
        sdrTotalAux2 = (self.dataCountAux2)*multiplier
        sdrTotal = sdrTotalAux1+sdrTotalMain+sdrTotalAux2
        #Total run times for each interval
        runTime = float((stop-timeStart).seconds*1000) + float((stop-timeStart).microseconds)/1000
        beforeStart = float((timeStart-timeStartRead).seconds*1000) + float((timeStart-timeStartRead).microseconds)/1000
        afterStop = float((stopRead-stop).seconds*1000) + float((stopRead-stop).microseconds)/1000
        ttlRunTime = float((stopRead-timeStartRead).seconds*1000) + float((stopRead-timeStartRead).microseconds)/1000
        #Real sampling frequency for experiment and for entire duration
        finalSmplFreq = int(round(float(sdrTotal)*1000/(ttlRunTime)))
        finalScanFreq = int(round(float(sdrTotal)*1000/(nCh*ttlRunTime)))
        finalSmplFreqExp = int(round(float(sdrTotalMain)*1000/(runTime)))
        finalScanFreqExp = int(round(float(sdrTotalMain)*1000/(nCh*runTime)))
        #Reconstructing when and where missed values occured
        missedBefore, missedDuring, missedAfter = 0, 0, 0
        if len(sdrMissedList) != 0:
	        for i in sdrMissedList:
	        	if i[1] <= float(int(beforeStart))/1000:
	        		missedBefore += i[0]
	        	elif i[1] > float(int(beforeStart))/1000 and i[1] <= float(int(beforeStart))/1000+float(int(runTime))/1000:
	        		missedDuring += i[0]
	        	elif i[1] > float(int(beforeStart))/1000+float(int(runTime))/1000 and i[1] <= float(int(beforeStart))/1000+float(int(runTime))/1000+float(int(afterStop))/1000:
	        		missedAfter += i[0]
        while True:
        	warning = False
        	if sdrMissed != 0:
        		warning = True
	        if runDone == 1:
	        	#Uncomment the following to see LJ Diagnostics, if needed.
	        	print "\n"+"#"*10+"\n[LABJACK REPORT]\n(this information is also saved in your data file)"
	        	print "__________________________________________________________________"
	        	print "                  | BEFORE | DURING EXPERIMENT | AFTER  |  TOTAL |"
	        	print "          TIME (s)|%s|     %s     |%s|%s|" % (printDigits(float(int(beforeStart))/1000,8),printDigits(float(int(runTime))/1000,9),
	        		printDigits(float(int(afterStop))/1000,8),printDigits(float(int(ttlRunTime))/1000,8))
	        	print "     SAMPLES TAKEN|%s|     %s     |%s|%s|" % (printDigits(sdrTotalAux1,8),printDigits(sdrTotalMain,9),printDigits(sdrTotalAux2,8),printDigits(sdrTotal,8))
	        	print "    SAMPLES MISSED|%s|     %s     |%s|%s|" % (printDigits(missedBefore,8),printDigits(missedDuring,9),printDigits(missedAfter,8),printDigits(sdrMissed,8))
	        	print "SAMPLING FREQ (Hz)|        |     %s     |        |%s|" % (printDigits(finalSmplFreqExp,9),printDigits(finalSmplFreq,8))
	        	print "    SCAN FREQ (Hz)|        |     %s     |        |%s|" % (printDigits(finalScanFreqExp,9),printDigits(finalScanFreq,8))
		        print "------------------------------------------------------------------"
		        print "*(Camera and Arduino are turned on only DURING_EXPERIMENT)"
		        print "#"*10
		        if warning:
		        	print
		        	print "#"*30
		        	print "!![ATTN]!! ---> The Labjack missed [%s] values! Please take a look at the labjack report." % sdrMissed
		        	print "           ---> You may wish to repeat this trial if many values were lost"
		        	print "           ---> You may also wish to reduce the labjack's SCAN_FREQUENCY after restarting the script."
		        	print "#"*30
		        	raw_input("Press [enter] to continue: ")
		        runDone = 2
		        break
			time.sleep(0.00001)
class readThread(threading.Thread):
	def __init__(self,sdr):
		threading.Thread.__init__(self)
		self.sdr = sdr
	def run(self):
		global chNum, nCh, ljSaveName, runDone, expName, sdrMissedList
		global sdrMissed, beforeStart, runTime, afterStop, ttlRunTime
		global sdrTotalAux1, sdrTotalAux2, sdrTotalMain, sdrTotal
		global finalSmplFreq, finalScanFreq, finalSmplFreqExp, finalScanFreqExp
		global missedBefore, missedDuring, missedAfter, hiddenOption
		sdrMissed, sdrMissedList = 0, []
		ljSaveName = "["+expName+"]-"+getDay(3)
		f = open(resultsDir+ljSaveName+".csv","w")
		for i in range(nCh):
			f.write("AIN"+str(chNum[i])+",")
		f.write("\n")
		while True:
			try:
				if not self.sdr.running:
					break
				result = self.sdr.data.get(True, 1)
				if result['errors'] != 0:
					sdrMissed += result['missed']
					missedTime = datetime.now()
					timeDiff = str((missedTime - timeStartRead).seconds*1000+(missedTime - timeStartRead).microseconds/1000)
					sdrMissedList.append([copy.deepcopy(result['missed']),copy.deepcopy(float(timeDiff)/1000)])
					print "\n>>>LabJack reported [%s] Errors: " % result['errors']
					print ">>>We lost [%s] values at [%sms] since Start." % (result['missed'], timeDiff)
					print ">>>If this continues, you may wish to reduce your LabJack SCAN_FREQUENCY after restarting the script."
				r = ljDAQ.processStreamData(result['result'])
				for each in range(len(r["AIN"+str(chNum[0])])):
					for i in range(nCh):
						f.write(str(r["AIN"+str(chNum[i])][each])+",")
					f.write("\n")
			except Queue.Empty:
				print "Queue is empty. Stopping..."
				self.sdr.running = False
				break
			except KeyboardInterrupt:
				self.sdr.running = False
			except Exception:
				e = sys.exc_info()[1]
				print type(e), e
				self.sdr.running = False
				break
		f.close()
		while True:
			if runDone == 2:
				if hiddenOption == "p":
					topLine = " , BEFORE EXP, DURING EXP, AFTER EXP, TOTAL, TRUE DATA CH,TRUE REF CH, ISOS DATA CH, ISOS REF CH, TRUE REF FREQ, ISOS REF FREQ\n"
					timeLine = "TIME (s),%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,\n" % (printDigits(float(int(beforeStart))/1000,8),
						printDigits(float(int(runTime))/1000,9), printDigits(float(int(afterStop))/1000,8),
						printDigits(float(int(ttlRunTime))/1000,8),photometryConfig1[0],photometryConfig1[1],
						photometryConfig1[2],photometryConfig1[3],photometryConfig2[0],photometryConfig2[1])
				else:
					topLine = " , BEFORE EXP, DURING EXP, AFTER EXP, TOTAL,\n"
					timeLine = "TIME (s),%s,%s,%s,%s,\n" % (printDigits(float(int(beforeStart))/1000,8),
						printDigits(float(int(runTime))/1000,9), printDigits(float(int(afterStop))/1000,8),
						printDigits(float(int(ttlRunTime))/1000,8))
				samplesLine = "SAMPLES TAKEN,%s,%s,%s,%s,\n" % (printDigits(sdrTotalAux1,8),printDigits(sdrTotalMain,9),
					printDigits(sdrTotalAux2,8),printDigits(sdrTotal,8))
				smplsMissedLine = "SAMPLES MISSED,%s,%s,%s,%s,\n" % (missedBefore, missedDuring, missedAfter, sdrMissed)
				smplFreqLine = "SAMPLING FREQ (HZ), ,%s, ,%s,\n" % (printDigits(finalSmplFreqExp,9),printDigits(finalSmplFreq,8))
				scanFreqLine = "SCAN FREQ (HZ), ,%s, ,%s,\n" % (printDigits(finalScanFreqExp,9),printDigits(finalScanFreq,8))
				stats = topLine+timeLine+samplesLine+smplsMissedLine+smplFreqLine+scanFreqLine
				with file(resultsDir+ljSaveName+".csv", "r") as original: data = original.read()
				with file(resultsDir+ljSaveName+".csv", "w") as modified: modified.write(stats + data)
				break
			time.sleep(0.00001)
####################
#GRAPHING RESULT DATA
def plotData():
	import plotly
	from plotly.graph_objs import Scatter, Layout, Figure
	import plotly.plotly as py
	import plotly.graph_objs as go
	global ttlRunTime
	linesTop = 6
	totalScans = -(1+linesTop)
	with open(resultsDir+ljSaveName+".csv") as fil:
		for line in fil:
			if line.strip():
				totalScans += 1
	axisTime, name, axisSignal, traces = [], [], {}, {}
	f = open(resultsDir+ljSaveName+".csv","r")
	for i in range(linesTop):
		f.readline()
	name = f.readline()[:-1].split(",")
	for i in range(nCh):
		axisSignal[i] = []
	timeSeg = float(float(ttlRunTime)/1000)/totalScans
	for i in range(totalScans):
		axisTime.append(i*timeSeg)
		hold = f.readline()[:-1].split(",")
		for i in range(nCh):
			axisSignal[i].append(hold[i])
	f.close()
	for i in range(nCh):
		traces[i] = go.Scatter(
			x = axisTime,
			y = axisSignal[i],
			name = "Channel "+name[i])
	data = []
	for i in range(nCh):
		data.append(traces[i])
	layout = go.Layout(
		title="\n"+ljSaveName,
		xaxis=dict(
			title="Time (s)"),
		yaxis=dict(
			title="Signal (V)"))
	plotly.offline.plot(
		{"data": data,
		"layout": layout})
####################
#CAMERA FUNCTION
def cameraSetup():
    c = fc2.Context()
    c.connect(*c.get_camera_from_index(0))
    c.set_video_mode_and_frame_rate(fc2.VIDEOMODE_640x480Y8, fc2.FRAMERATE_30)
    p = c.get_property(fc2.FRAME_RATE)
    c.set_property(**p)
    c.start_capture()
    return c
def cameraRecord(name,c,numFrames):
    c.set_strobe_mode(3, True, 1, 0, 10)
    c.openAVI(name, frate=30, bitrate=1000000)
    for i in range(numFrames):
        c.appendAVI()
    c.set_strobe_mode(3, False, 1, 0, 10)
    while True:
    	time.sleep(0.00001)
    	if runDone == 2:
    		break
    c.closeAVI()
def cameraClose(c):
    c.stop_capture()
    c.disconnect()
class cameraThread(threading.Thread):
	def __init__(self):
		threading.Thread.__init__(self)
	def run(self):
		global cameraSaveName, packet, cameraCtx, expName, resultsDir
		cameraSaveName = "["+expName+"]-"+getDay(3)
		numFrames = (packet[3]/1000)*30
		cameraRecord(resultsDir+cameraSaveName, cameraCtx, numFrames)
##############################################################################################################
#=================================================PROGRAM====================================================#
##############################################################################################################
####################
#ARDUINO CNTRL VARIABLES
serPort, baudRate = "", 115200
userhome = os.path.expanduser('~')
baseDir = userhome+"/desktop/arduinoControl/"
presetDir = baseDir+"UserPresets/"
prgmDir = baseDir+"prgmSettings/"
saveDir = baseDir+"outputSaves/"
settings = "enter_new"
startMarker, endMarker = 60, 62
timeOffset = 3600*4 #EST = -4 hours.
fullscreenMsg = ""
num_loops, reset, mainLoopbrk = 0, 0, 0
prevTimeStart, prevTimeStartRead = datetime.now(), datetime.now()
timeStart, timeStartRead = copy.deepcopy(prevTimeStart), copy.deepcopy(prevTimeStartRead)
runDone = 0
####################

#SETUP LABJACK DAQ and PTGREY CAMERA
cameraCtx = cameraSetup()

####################
#MAIN PROGRAM LOOP
while mainLoopbrk == 0:
	####################
	#TO SETUP OR NOT TO SETUP
	if num_loops == 0:
		settings = "enter_new"
	while not num_loops == 0:
		ask_user = raw_input("Run Setup Again? 'N' to use previous settings. (Y/N): ").lower()
		if ask_user == "y":
			settings = "enter_new"
			break
		elif ask_user == "n":
			settings = "use_old"
			break
		else:
			print "Type (Y/N) to Continue"
	####################
	#GET INPUTS. START SERIAL
	run_setup(settings)
	startSerial()
	if mainLoopbrk == 1:
		break
	####################
	#SEND DATA
	sysTime = ["<L",calendar.timegm(time.gmtime())-timeOffset]
	pwm_packSend = []
	for i in pwm_pack:
		period = (float(1000000)/float(i[4]))
		cycleTimeOn = long(round(period*(float(i[7])/float(100))))
		cycleTimeOff = long(round(period*(float(1)-((float(i[7])/float(100))))))
		timePhaseShift = long(round(period*(float(i[6])/float(360))))
		pwm_packSend.append(["<LLLLLBL",0,i[2],i[3],cycleTimeOn,cycleTimeOff,i[5],timePhaseShift])
	allowExp = 0
	try:
		sendPackets([sysTime],[packet],tone_pack,out_pack,pwm_packSend)
		ljDAQ = LJU6()
		ljDAQ = startLJ(ljDAQ)
		sdr = StreamDataReader(ljDAQ)
		sdrThread = threading.Thread(target = sdr.readStreamData)
		dataReading = readThread(sdr)
		cameraRun = cameraThread()
		MAX_REQUESTS = int(math.ceil((float(scanFreq*nCh*packet[3]/1000)/float(packsPerReq*smplsPerPack))))
		SMALL_REQUEST = int(round((float(scanFreq*nCh*0.5)/float(packsPerReq*smplsPerPack))))
		#USER TRIGGER
		raw_input("Press 'Enter' To Begin ")
		#RUN
		allowExp = 1
		if allowExp == 1:
			runDone = 0
			sdrThread.start()
			while True:
				if timeStartRead != prevTimeStartRead:
					prevTimeStartRead = timeStartRead
					break
				time.sleep(0.00001)
			dataReading.start()
			while True:
				if timeStart != prevTimeStart:
					prevTimeStart = timeStart
					break
				time.sleep(0.00001)
			cameraRun.start()
			runExperiment()
	#except (LabJackPython.NullHandleException, LabJackPython.LabJackException):
	#	print gfxBar(40)
	#	print "[ATTN]: Please make sure the LabJack is connected."
	#	raw_input("Reconnect the hardware and press [enter] to try again: ")
	#	ser.setDTR(False) 
	#	time.sleep(0.022)
	#	reset = 1
	#	num_loops += 1
	#	allowExp = 0
	except serial.serialutil.SerialException:
		print gfxBar(40)
		print "[ATTN]: The Arduino became disconnected before data could be sent."
		raw_input("Reconnect the hardware and press [enter] to try again: ")
		reset = 1
		num_loops += 1
		allowExp = 0
	####################
	#END
####################