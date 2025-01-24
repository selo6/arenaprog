// Arena firmware
// Copyright (C) 2025 DEV Joni / Joni Kemppainen
// Licence: GPLv3-only
//
// Tested running on Arduino Nano Every

// Clean up these notes
// --------------------
// 10 l vastaa 4.3 mm -> 4.3 mm per l
// 5 l 2.2mm -> 0.44 mm per l
// 20 l 8.9mmm -> 0.445mm per l
// -> 0.44mm per l
// 100l 34.3 mm -> 0.343 mm per l


#include "AccelStepper.h"

const int p_m1 = 2;
const int p_m2 = 4;
const int p_m3 = 3;
const int p_m4 = 5;

const int p_led1 = 6;
const int p_led2 = 7;
const int p_led3 = 8;
const int p_led4 = 9;
const int p_led5 = 10;
const int p_led6 = 11;

AccelStepper motor(8, p_m1, p_m2, p_m3, p_m4);

long endpos = -25000;

long pos = 0;
int message = 0;

void setup() {
	
	Serial.begin(9600);
	
	pinMode(p_led1, OUTPUT);
	pinMode(p_led2, OUTPUT);
	pinMode(p_led3, OUTPUT);
	pinMode(p_led4, OUTPUT);
	pinMode(p_led5, OUTPUT);
	pinMode(p_led6, OUTPUT);

	motor.setMaxSpeed(1300.);
	motor.setAcceleration(1000.);
	motor.setSpeed(500);
}
void loop() {

	if (Serial.available() > 0) {
		message = Serial.read();
		
		if (message==114) {
			motor.setMaxSpeed(1300.);
			motor.setAcceleration(1000.);
			pos += 500;
			motor.moveTo(pos);
			Serial.println("Raising");
		}
		else if (message==108) {
			motor.setMaxSpeed(1300.);
			motor.setAcceleration(1000.);
			pos -= 500;
			motor.moveTo(pos);
			Serial.println("Lowering");
		}
		else if (message=='x') {
			motor.setAcceleration(10000.);
			motor.setMaxSpeed(2500.);
			pos -= 250;
			motor.moveTo(pos);
			Serial.println("Low end ram");
		}
		else if (message=='A') {
			digitalWrite(p_led1, 1);
			Serial.println("LED1-on");
		}
		else if (message=='B') {
			digitalWrite(p_led2, 1);
			Serial.println("LED2-on");
		}
		else if (message=='C') {
			digitalWrite(p_led3, 1);
			Serial.println("LED3-on");
		}
		else if (message=='D') {
			digitalWrite(p_led4, 1);
			Serial.println("LED4-on");
		}
		else if (message=='E') {
			digitalWrite(p_led5, 1);
			Serial.println("LED5-on");
		}
		else if (message=='F') {
			digitalWrite(p_led6, 1);
			Serial.println("LED6-on");
		}
		
		else if (message=='a') {
			digitalWrite(p_led1, 0);
			Serial.println("LED1-off");
		}
		else if (message=='b') {
			digitalWrite(p_led2, 0);
			Serial.println("LED2-off");
		}
		else if (message=='c') {
			digitalWrite(p_led3, 0);
			Serial.println("LED3-off");
		}
		else if (message=='d') {
			digitalWrite(p_led4, 0);
			Serial.println("LED4-off");
		}
		else if (message=='e') {
			digitalWrite(p_led5, 0);
			Serial.println("LED5-off");
		}
		else if (message=='f') {
			digitalWrite(p_led6, 0);
			Serial.println("LED6-off");
		}
	
		else {

			Serial.println("Unkown command");
		}
	}

	motor.run();
}
