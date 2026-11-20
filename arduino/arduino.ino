/*
 * ==============================================================================
 * Project: FogGuard — Low-Latency Ultrasonic Obstacle Detection & ADAS HUD
 * Module: Canonical High-Performance Interrupt-Driven (PCINT) Firmware
 * Target: Arduino Uno / Nano (ATmega328P)
 * Baud: 115200 baud
 *
 * Real-Time Architecture:
 * - Pin Change Interrupts (PCINT2_vect on Port D, pins 2..7):
 *   Captures ultrasonic ECHO rising and falling edges with microsecond precision.
 *   Zero blocking while waiting for echoes.
 * - Non-blocking round-robin ultrasonic state machine:
 *   Staggers sensor triggers by 25 ms (the physical propagation limit for 400 cm
 *   plus acoustic reverberation / decay damping to eliminate ghost echoes).
 * - High-speed JSON telemetry transmission:
 *   Transmits a single, coherent, compact JSON telemetry frame per sweep:
 *   {"seq":1024,"up":45120,"traffic":"GREEN","dur":25,"sensors":[...]}
 *   Includes sequence number, device uptime, and all sensors (with null if no echo).
 * - Physical Update Rates:
 *   - 4-sensor configuration (default): 10.0 Hz (100 ms full sweep)
 *   - 6-sensor configuration:          6.67 Hz (150 ms full sweep)
 * ==============================================================================
 */

#include <Arduino.h>

// ─── Physical Sensor Configuration ──────────────────────────────────────────
// Set to 4 for 10.0 Hz (100 ms period) or 6 for 6.67 Hz (150 ms period)
#define SENSOR_COUNT 6

  const uint8_t TRIG_PINS[6] = {10, 13, 9, 12, 11, 8};
  const uint8_t ECHO_PINS[6] = {4, 7, 3, 6, 5, 2}; // Port D pins 2..7 (PCINT18..23)
  const char* SENSOR_IDS[6] = {"S1", "S2", "S3", "S4", "S5", "S6"};
  const char* SENSOR_ZONES[6] = {
    "front_left",
    "front_center_left",
    "front_center_right",
    "front_right",
    "left_side",
    "right_side"
  };
  const unsigned long TELEMETRY_INTERVAL_MS = 150; // 6.67 Hz for 6 sensors (speed-of-sound limit)

// ─── Ultrasonic Physics & Thresholds ─────────────────────────────────────────
// Speed of sound at 20°C: ~343 m/s = 0.0343 cm/us (58.3 us/cm round trip)
// 400 cm * 58.3 us/cm = 23,320 us max round-trip echo travel time.
const unsigned long ECHO_TIMEOUT_US     = 23320UL; // 400 cm maximum window
const unsigned long MIN_ECHO_US        = 116UL;   // ~2 cm physical limit
const float         MIN_DISTANCE_CM    = 2.0;
const float         MAX_DISTANCE_CM    = 400.0;
const float         CAUTION_THRESHOLD_CM = 150.0;

// Inter-sensor trigger stagger: 25 ms allows echo travel (23.3 ms) + 1.7 ms acoustic decay
const unsigned long SENSOR_STEP_INTERVAL_MS = 25;

// ─── Traffic Signal Definitions ──────────────────────────────────────────────
const uint8_t PIN_LED_RED    = A0;
const uint8_t PIN_LED_YELLOW = A1;
const uint8_t PIN_LED_GREEN  = A2;

const unsigned long DURATION_RED    = 30; // Seconds
const unsigned long DURATION_GREEN  = 25; // Seconds
const unsigned long DURATION_YELLOW = 5;  // Seconds

enum TrafficState { STATE_RED, STATE_GREEN, STATE_YELLOW };
TrafficState currentTrafficState = STATE_RED;
unsigned long trafficStateStartTime = 0;

// ─── Interrupt Echo Storage (Atomic access via cli/sei) ──────────────────────
volatile unsigned long echoStartTime[SENSOR_COUNT];
volatile unsigned long echoEndTime[SENSOR_COUNT];
volatile bool echoReceived[SENSOR_COUNT];
volatile bool echoMeasuring[SENSOR_COUNT];
volatile uint8_t previousPinDState = 0;

// Filtered calculated distances
float currentDistances[SENSOR_COUNT];
bool  obstacleDetected[SENSOR_COUNT];

// Telemetry & Sequencer State
uint8_t currentSensorIndex = 0;
unsigned long lastTriggerTime = 0;
unsigned long lastTelemetryBroadcast = 0;
unsigned long telemetrySeq = 0;

// ─── Pin Change Interrupt Service Routine for Port D (Pins D0-D7) ────────────
ISR(PCINT2_vect) {
  uint8_t currentPinD = PIND;
  uint8_t changedPins = currentPinD ^ previousPinDState;
  unsigned long now = micros();

  // Inspect each configured echo pin (D2 through D5 or D7)
  for (uint8_t i = 0; i < SENSOR_COUNT; i++) {
    uint8_t pinBit = 1 << ECHO_PINS[i];
    if (changedPins & pinBit) {
      if (currentPinD & pinBit) {
        // Rising edge: pulse began
        echoStartTime[i] = now;
        echoMeasuring[i] = true;
      } else if (echoMeasuring[i]) {
        // Falling edge: pulse completed
        echoEndTime[i] = now;
        echoReceived[i] = true;
        echoMeasuring[i] = false;
      }
    }
  }

  previousPinDState = currentPinD;
}

// ─── Trigger Next Ultrasonic Sensor ──────────────────────────────────────────
void triggerSensor(uint8_t index) {
  // Clear measurement flags atomically
  cli();
  echoReceived[index]  = false;
  echoMeasuring[index] = false;
  echoStartTime[index] = 0;
  echoEndTime[index]   = 0;
  sei();

  // 10 microsecond trigger pulse
  digitalWrite(TRIG_PINS[index], LOW);
  delayMicroseconds(2);
  digitalWrite(TRIG_PINS[index], HIGH);
  delayMicroseconds(10);
  digitalWrite(TRIG_PINS[index], LOW);

  lastTriggerTime = millis();
}

// ─── Calculate Distance for Previously Triggered Sensor ──────────────────────
void processSensorResult(uint8_t index) {
  unsigned long start, end;
  bool received;

  cli();
  start = echoStartTime[index];
  end = echoEndTime[index];
  received = echoReceived[index];
  echoReceived[index] = false;
  sei();

  if (received && (end > start)) {
    unsigned long pulseDuration = end - start;
    if (pulseDuration >= MIN_ECHO_US && pulseDuration <= ECHO_TIMEOUT_US) {
      // Speed of sound: duration / 58.0 us per cm
      float dist = (float)pulseDuration / 58.0;
      if (dist >= MIN_DISTANCE_CM && dist <= MAX_DISTANCE_CM) {
        currentDistances[index] = dist;
        obstacleDetected[index] = (dist <= CAUTION_THRESHOLD_CM);
        return;
      }
    }
  }

  // No valid echo received or out of valid physical range
  currentDistances[index] = -1.0;
  obstacleDetected[index] = false;
}

// ─── Traffic Signal Controller ───────────────────────────────────────────────
void setTrafficLeds(TrafficState state) {
  digitalWrite(PIN_LED_RED,    state == STATE_RED    ? HIGH : LOW);
  digitalWrite(PIN_LED_YELLOW, state == STATE_YELLOW ? HIGH : LOW);
  digitalWrite(PIN_LED_GREEN,  state == STATE_GREEN  ? HIGH : LOW);
}

const char* getTrafficStateName(TrafficState state) {
  switch (state) {
    case STATE_RED:    return "RED";
    case STATE_YELLOW: return "YELLOW";
    case STATE_GREEN:  return "GREEN";
    default:           return "UNKNOWN";
  }
}

unsigned long getTrafficStateDuration(TrafficState state) {
  switch (state) {
    case STATE_RED:    return DURATION_RED;
    case STATE_YELLOW: return DURATION_YELLOW;
    case STATE_GREEN:  return DURATION_GREEN;
    default:           return 0;
  }
}

void updateTrafficSignal() {
  unsigned long elapsedSec = (millis() - trafficStateStartTime) / 1000;
  unsigned long currentDuration = getTrafficStateDuration(currentTrafficState);

  if (elapsedSec >= currentDuration) {
    switch (currentTrafficState) {
      case STATE_RED:    currentTrafficState = STATE_GREEN;  break;
      case STATE_GREEN:  currentTrafficState = STATE_YELLOW; break;
      case STATE_YELLOW: currentTrafficState = STATE_RED;    break;
    }
    trafficStateStartTime = millis();
    setTrafficLeds(currentTrafficState);
  }
}

// ─── Single Compact JSON Telemetry Frame Transmission ────────────────────────
void broadcastTelemetry() {
  unsigned long now = millis();
  telemetrySeq++;

  // Emit a single compact JSON-line:
  // {"seq":1,"up":1234,"traffic":"RED","dur":30,"sensors":[{"id":"S1","zone":"front_left","dist":45.2,"det":true},...]}
  Serial.print("{\"seq\":");
  Serial.print(telemetrySeq);
  Serial.print(",\"up\":");
  Serial.print(now);
  Serial.print(",\"traffic\":\"");
  Serial.print(getTrafficStateName(currentTrafficState));
  Serial.print("\",\"dur\":");
  Serial.print(getTrafficStateDuration(currentTrafficState));
  Serial.print(",\"sensors\":[");

  for (uint8_t i = 0; i < SENSOR_COUNT; i++) {
    if (i > 0) Serial.print(",");
    Serial.print("{\"id\":\"");
    Serial.print(SENSOR_IDS[i]);
    Serial.print("\",\"zone\":\"");
    Serial.print(SENSOR_ZONES[i]);
    Serial.print("\",\"dist\":");
    if (currentDistances[i] > 0) {
      Serial.print(currentDistances[i], 1);
    } else {
      Serial.print("null");
    }
    Serial.print(",\"det\":");
    Serial.print(obstacleDetected[i] ? "true" : "false");
    Serial.print("}");
  }

  Serial.println("]}");
}

// ─── Arduino Setup ───────────────────────────────────────────────────────────
void setup() {
  // Use high-speed 115200 baud to eliminate serial transmission latency
  Serial.begin(115200);

  // Initialize Ultrasonic Pins
  for (uint8_t i = 0; i < SENSOR_COUNT; i++) {
    pinMode(TRIG_PINS[i], OUTPUT);
    digitalWrite(TRIG_PINS[i], LOW);
    pinMode(ECHO_PINS[i], INPUT);
    currentDistances[i] = -1.0;
    obstacleDetected[i] = false;
  }

  // Initialize Traffic Signal LED Pins
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_LED_YELLOW, OUTPUT);
  pinMode(PIN_LED_GREEN, OUTPUT);

  // Record initial Port D state
  previousPinDState = PIND;

  // Configure Pin Change Interrupts on Port D (PCINT2 group covers D0-D7)
  PCICR |= (1 << PCIE2);

  // Unmask the echo pins: D2..D5 for 4 sensors, D2..D7 for 6 sensors
  uint8_t mask = 0;
  for (uint8_t i = 0; i < SENSOR_COUNT; i++) {
    // ECHO_PINS are on Port D, pin 2 is PCINT18, pin 3 is PCINT19, etc.
    mask |= (1 << (PCINT18 + (ECHO_PINS[i] - 2)));
  }
  PCMSK2 |= mask;

  // Initialize traffic state
  trafficStateStartTime = millis();
  setTrafficLeds(currentTrafficState);

  // Trigger the first sensor
  triggerSensor(0);
}

// ─── Main Real-Time Loop (Zero Blocking Delays) ──────────────────────────────
void loop() {
  unsigned long now = millis();

  // 1. Service Traffic Signal State Machine
  updateTrafficSignal();

  // 2. Round-Robin Sensor Sequencer (25 ms per sensor step)
  if (now - lastTriggerTime >= SENSOR_STEP_INTERVAL_MS) {
    // Process results from previously triggered sensor
    processSensorResult(currentSensorIndex);

    // Advance to next sensor
    currentSensorIndex = (currentSensorIndex + 1) % SENSOR_COUNT;

    // Trigger next sensor
    triggerSensor(currentSensorIndex);
  }

  // 3. Telemetry Broadcast at Target Frequency (10 Hz for 4 sensors)
  if (now - lastTelemetryBroadcast >= TELEMETRY_INTERVAL_MS) {
    lastTelemetryBroadcast = now;
    broadcastTelemetry();
  }
}