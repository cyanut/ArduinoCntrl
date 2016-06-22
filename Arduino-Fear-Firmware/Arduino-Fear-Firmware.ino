//#############################################################################
//To be used with FearControl.py
//#######################################

//#######################################
//Libraries
#include <NewTone.h>
#include <TimeLib.h>
//#######################################

//#######################################
//Misc. Variables
boolean askForData = true; //Request New Data
unsigned long startTime; //Use millis() at end of setup() to ensure time counting starts at beginning of loop()
unsigned long startMicros; //Use micros() at end of setup() to ensure time counting starts at start of loop() for pwm.
int i = 0; //print end message once
//##############################################################################

//##############################################################################
//#######################################
//This grabs time from computer
union pctime {
  unsigned long pcTime;
  byte pctimeData[4];
};
pctime pcTimeData;
byte setupTimeStore[4];
//#######################################

//#######################################
//This manages setup initialization instructions
struct setupData {
  byte pinsD;
  byte pinsB;
  unsigned long total_time;
  unsigned int num_tones;
  unsigned int num_outd07;
  unsigned int num_pwmb813;
};
union pcsetup {
  setupData data;
  byte pcsetupData[12];
};
pcsetup pcSetupData;
byte setupDataStore[12];
//#######################################

//#######################################
//This manages tone instructions
struct toneData {
  unsigned long tone_on;
  unsigned long tone_off;
  unsigned int freq;
};
union pcTone {
  toneData data;
  byte pctoneData[10];
};
pcTone pcToneData[15];
byte toneDataStore[10];
//#######################################

//#######################################
//This manages simple output instructions
struct outData {
  unsigned long time_to_trigger;
  byte pins;
};
union pcout {
  outData data;
  byte pcoutData[5];
};
pcout out_d07[30];
byte pcoutd07[5];
byte nowState[30];
//#######################################

//#######################################
//This manages pwm/frequency output instructions
struct pwmData {
  unsigned long startMillis;
  unsigned long time_on;
  unsigned long time_off;
  unsigned long cycleTimeOn;
  unsigned long cycleTimeOff;
  byte pins;
  unsigned long timePhaseShift;
};
union pcpwm {
  pwmData data;
  byte pcpwmData[25];
};
pcpwm pwm_b813[33];
byte pcpwmb813[25];
byte cycleCheck[33] = {0};
//#######################################
//##############################################################################

//##############################################################################
//SETUP
void setup(){
  //#######################################
  //Setting up SERIAL
  Serial.begin(115200);
  //BEFOR STARTING, PINS SHOULD BE LOW
   DDRD = 255;
   DDRB = 255;
   PORTD = B0;
   PORTB = B0;
  //READY TO BEGIN RECEIVING DATA
  Serial.println("<Arduino is ready>>");
  //#######################################
  //GET THE TIME
  requestData();
  delay(100);
      if (Serial.available() < 4){
        return;
      }
      for (byte n = 0; n < 4; n++){
        setupTimeStore[n] = Serial.read();
      }
      for (byte n = 0; n < 4; n++){
        pcTimeData.pctimeData[n] = setupTimeStore[n];
      }
  setTime(pcTimeData.pcTime+1);
  askForData = true;
  //#######################################
  //INITIALIZING DATA
  requestData();
  delay(100); //Allow small delay for data to arrive
    //RECEIVE AND STORE IN DATA STRUCT
      if (Serial.available() < 12) {
         return;
      }
      for (byte n = 0; n < 12; n++) {
         setupDataStore[n] = Serial.read();
      }
      for (byte n = 0; n < 12; n++) {
         pcSetupData.pcsetupData[n] = setupDataStore[n];
      }
   askForData = true;
   //#######################################
   
   //#######################################
   //TONE DATA
   for (int i=0; i<pcSetupData.data.num_tones;i++){
     requestData();
     delay(100);
         if (Serial.available() < 10) {
             return;
         }
         for (byte n = 0; n < 10; n++) {
             toneDataStore[n] = Serial.read();
         }
         for (byte n = 0; n < 10; n++) {
             pcToneData[i].pctoneData[n] = toneDataStore[n];
         } 
     askForData = true;
   }
   //#######################################
   
   //#######################################
   //OUTPUT DATA (on D register)
   byte prevState = B0;
   for (int i=0; i<pcSetupData.data.num_outd07; i++){
     requestData();
     delay(100);
         if (Serial.available() < 5) {
             return;
         }
         for (byte n = 0; n < 5; n++) {
             pcoutd07[n] = Serial.read();
         }
         for (byte n = 0; n < 5; n++) {
             out_d07[i].pcoutData[n] = pcoutd07[n];
         }
     askForData = true;
     nowState[i] = prevState^out_d07[i].data.pins;
     prevState = nowState[i];
   }
   //#######################################
   
   //#######################################
   //PWM/FREQ MODULATION DATA (on B register)
   for (int i=0; i<pcSetupData.data.num_pwmb813; i++){
     requestData();
     delay(100);
       if (Serial.available() < 25) {
           return;
       }
       for (byte n = 0; n < 25; n++) {
           pcpwmb813[n] = Serial.read();
       }
       for (byte n = 0; n < 25; n++) {
           pwm_b813[i].pcpwmData[n] = pcpwmb813[n];
       }
   askForData = true;
   }
   //#######################################
   
   //#######################################
   //PIN Initialization
   DDRD = pcSetupData.data.pinsD;
   DDRB = pcSetupData.data.pinsB;
   PORTD = B0;
   PORTB = B0;
   //Everything is now ready to go; awaiting user trigger (from computer)
   while (true){
    if (Serial.available() > 0) {
      break;
    }
    else {
      delay(50);
      continue;
    }
   }
   //Timestamp current time from Arduino
   Serial.print("<");
   Serial.print(millis());
   Serial.print(",");
   ardTime();
   Serial.print(">");
   //Almost done
   startMicros = micros();
   startTime = millis();//Use startTime as reference instead of millis()
   //#######################################
}
//##############################################################################

//##############################################################################
//MAIN PROGRAM
void loop() {
  //#######################################
  //TONE LOOP. 
  //NOTE: Pin 10 is assigned to TONE Exclusively. Do NOT use for PWM/other Freq Modulation
  for (int i=0; i<pcSetupData.data.num_tones;i++){
    if (pcToneData[i].data.tone_on <= (millis()-startTime) && pcToneData[i].data.tone_off > (millis()-startTime)){
      NewTone(10,pcToneData[i].data.freq);
    }
    else if (pcToneData[i].data.tone_off <= (millis()-startTime) && pcToneData[i+1].data.tone_on > (millis()-startTime)){
      noNewTone(10);
    }
    else if (pcToneData[pcSetupData.data.num_tones-1].data.tone_off <= (millis()-startTime)){
      noNewTone(10);
    }
  }
  //#######################################

  //#######################################
  //OUTPUT LOOP (on D register)
  for (int i=0; i<pcSetupData.data.num_outd07; i++) {
    if (out_d07[i].data.time_to_trigger <= (millis()-startTime) && out_d07[i+1].data.time_to_trigger > (millis()-startTime)){
      PORTD = nowState[i];
    }
    else if (out_d07[pcSetupData.data.num_outd07-1].data.time_to_trigger <= (millis()-startTime)){
      PORTD = B0;
    }
  }
  //#######################################

  //#######################################
  for (int i=0; i<pcSetupData.data.num_pwmb813; i++) {
    if (pwm_b813[i].data.time_on <= (millis()-startTime) && pwm_b813[i].data.time_off > (millis()-startTime)){
        if (cycleCheck[i] == 0){
          if (cycleCheckMicros(&pwm_b813[i].data.startMillis,pwm_b813[i].data.timePhaseShift)){
            PORTB = PORTB^byte(pwm_b813[i].data.pins);
            cycleCheck[i] = 1;
          }
        }
        if (cycleCheck[i] == 1){
          if (cycleCheckMicros(&pwm_b813[i].data.startMillis, pwm_b813[i].data.cycleTimeOn)){
            PORTB = PORTB^byte(pwm_b813[i].data.pins);
            cycleCheck[i] = 2;
          }
        }
        if (cycleCheck[i] == 2){
          if (cycleCheckMicros(&pwm_b813[i].data.startMillis, pwm_b813[i].data.cycleTimeOff)){
            PORTB = PORTB^byte(pwm_b813[i].data.pins);
            cycleCheck[i] = 1;
          }
        }
    }
    else if (pwm_b813[i].data.time_off <= (millis()-startTime) && pwm_b813[i+1].data.time_on > (millis()-startTime)){
      PORTB = PORTB&(~byte(pwm_b813[i].data.pins));
    }
    else if (pwm_b813[pcSetupData.data.num_pwmb813-1].data.time_off <= (millis()-startTime)){
      PORTB = PORTB&(~byte(pwm_b813[i].data.pins));
    }
  }
  //#######################################
  
  //#######################################
  //FINISHING EXPERIMENT AND REPORTING TIME.
  if (millis()-startTime >= pcSetupData.data.total_time) {
     if (i == 0) {
       Serial.print("<");
       Serial.print(millis()-startTime);
       Serial.print(",");
       ardTime();
       Serial.print(">");
       i++;
      }
  }
  //#######################################
}
//##############################################################################

//##############################################################################
//Misc. Functions
  //#######################################
  //Requesting Data
  void requestData() {
     if (askForData) {
       Serial.print("<M>");
       askForData = false;
     }
  }
  //#######################################
  
  //#######################################
  //Non-Tone (i.e. high Frequency) frequency modulation logic
  boolean cycleCheckMicros(unsigned long *lastMicros, unsigned long CycleTime) 
  {
   unsigned long currentMicros = (micros()-startMicros);
   if(currentMicros - *lastMicros >= CycleTime){
     *lastMicros = currentMicros;
     return true;
   }
   else
     return false;
  }
  //#######################################
  
  //#######################################
  //Time from Arduino
  void ardTime(){
    printDigits(hour());
    Serial.print(':');
    printDigits(minute());
    Serial.print(':');
    printDigits(second());
  }
  //#######################################
  
  //#######################################
  //Prints minutes and seconds with 2 spaces
  void printDigits(int digits){
    if (digits < 10) {
      Serial.print("0");
    }
    Serial.print(digits);
  }
  //#######################################
//##############################################################################
