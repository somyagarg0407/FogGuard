
// byte ensures it takes 1 byte instead of standart 2 bytes unneccesarily
// If u change these numbers (For ECHO ONLY) u must change the interrupt reciever as well (PCMSK2)
const byte TRIG_1 = 9;
const byte ECHO_1 = 2;

const byte TRIG_2 = 10;
const byte ECHO_2 = 3;

const byte TRIG_3 = 11;
const byte ECHO_3 = 4;

const byte TRIG_4 = 12;
const byte ECHO_4 = 5;

// volatile used to say that this value can abruptly change
// Some times it might reject abrupt changes as accidental in default var types
volatile unsigned long startTime[4] = {0, 0, 0, 0};
volatile unsigned long endTime[4] = {0, 0, 0, 0};
volatile byte previousState = 0;

void setup() {
  Serial.begin(115200);  // Higher baud rate for faster transmission

  // Enable the interrupts of pins D0 - D7
  PCIR |= (1 << PCIE2);  // PCIR is the register and PCEIR is the interrupt handler of D0-D7

  PCMSK2 |= (1 << PCINT18);  // D2
  PCMSK2 |= (1 << PCINT19);  // D3
  PCMSK2 |= (1 << PCINT20);  // D4
  PCMSK2 |= (1 << PCINT21);  // D5

  pinMode(TRIG_1, OUTPUT);
  pinMode(ECHO_1, INPUT);

  pinMode(TRIG_2, OUTPUT);
  pinMode(ECHO_2, INPUT);

  pinMode(TRIG_3, OUTPUT);
  pinMode(ECHO_3, INPUT);

  pinMode(TRIG_4, OUTPUT);
  pinMode(ECHO_4, INPUT);

}

void loop() {
  digitalWrite(TRIG_1, HIGH);
  delayMicroseconds(10);

  digitalWrite(TRIG_1, LOW);
  delay(1000);
}

ISR(PCINT2_vect){
  byte currentstate = PIND;
  byte changedPins = currentState ^ previousState;

  if (changedPins & (1 << 2){
    if (currentState & (1 << 2)){
      startTime[0] = micros();
    }
    else {
      endTime[0] = micros();
    }
  }

  if (changedPins & (1 << 3){
    if (currentState & (1 << 3)){
      startTime[0] = micros();
    }
    else {
      endTime[0] = micros();
    }
  }

  if (changedPins & (1 << 4){
    if (currentState & (1 << 4)){
      startTime[0] = micros();
    }
    else {
      endTime[0] = micros();
    }
  }

  if (changedPins & (1 << 5){
    if (currentState & (1 << 5)){
      startTime[0] = micros();
    }
    else {
      endTime[0] = micros();
    }
  }

}
