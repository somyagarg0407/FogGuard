#include <Arduino.h>

// ============================================================================
// 1. HARDWARE PIN CONFIGURATION
// ============================================================================
// Note: GPIO 34-39 are input-only on ESP32-WROOM-32 and cannot drive LEDs.
// GPIO 25, 33, and 32 are full bidirectional output-capable pins.
constexpr uint8_t PIN_LED_RED    = 25;
constexpr uint8_t PIN_LED_YELLOW = 33;
constexpr uint8_t PIN_LED_GREEN  = 32;

// ============================================================================
// 2. CONFIGURABLE SIGNAL DURATIONS (IN SECONDS)
// ============================================================================
constexpr uint32_t DURATION_RED_SEC    = 5;
constexpr uint32_t DURATION_GREEN_SEC  = 5;
constexpr uint32_t DURATION_YELLOW_SEC = 2;

// ============================================================================
// 3. SERIAL & TIMING CONSTANTS
// ============================================================================
constexpr uint32_t SERIAL_BAUD_RATE    = 115200;
constexpr uint32_t TICK_INTERVAL_MS    = 1000; // 1-second countdown resolution

// Set to true if you want human-readable logs alongside JSON, false for pure JSONL
constexpr bool ENABLE_HUMAN_DEBUG_LOG  = false; 

// ============================================================================
// 4. TRAFFIC STATE MACHINE DEFINITION
// ============================================================================
enum class TrafficState : uint8_t {
  RED = 0,
  GREEN,
  YELLOW
};

// State variables
TrafficState currentState = TrafficState::RED;
uint32_t remainingSeconds = DURATION_RED_SEC;
uint32_t lastTickMillis   = 0;

// ============================================================================
// 5. HELPER FUNCTIONS
// ============================================================================

/**
 * Safely switches physical LED outputs so only one LED is active at any time.
 */
void applyLedOutputs(TrafficState state) {
  // Turn all LEDs OFF first to prevent brief overlap during transitions
  digitalWrite(PIN_LED_RED, LOW);
  digitalWrite(PIN_LED_YELLOW, LOW);
  digitalWrite(PIN_LED_GREEN, LOW);

  // Activate the target LED
  switch (state) {
    case TrafficState::RED:
      digitalWrite(PIN_LED_RED, HIGH);
      break;
    case TrafficState::GREEN:
      digitalWrite(PIN_LED_GREEN, HIGH);
      break;
    case TrafficState::YELLOW:
      digitalWrite(PIN_LED_YELLOW, HIGH);
      break;
  }
}

/**
 * Converts the enum state into a strict string literal for JSON serialization.
 */
const char* getStateName(TrafficState state) {
  switch (state) {
    case TrafficState::RED:    return "RED";
    case TrafficState::GREEN:  return "GREEN";
    case TrafficState::YELLOW: return "YELLOW";
    default:                   return "RED";
  }
}

/**
 * Transmits a single newline-terminated JSON object (JSON Lines protocol).
 */
void transmitTelemetry(TrafficState state, uint32_t secondsLeft) {
  const char* stateStr = getStateName(state);

  // Fixed 96-byte buffer prevents dynamic memory fragmentation
  char jsonBuffer[96];
  snprintf(
    jsonBuffer,
    sizeof(jsonBuffer),
    "{\"module\":\"traffic_signal\",\"state\":\"%s\",\"remaining_seconds\":%lu}",
    stateStr,
    static_cast<unsigned long>(secondsLeft)
  );

  Serial.println(jsonBuffer);

  if (ENABLE_HUMAN_DEBUG_LOG) {
    Serial.printf("Traffic Signal: %s | Remaining: %lu\n", stateStr, static_cast<unsigned long>(secondsLeft));
  }
}

/**
 * Advances the state machine following the strict cycle: RED -> GREEN -> YELLOW -> RED
 */
void advanceTrafficState() {
  switch (currentState) {
    case TrafficState::RED:
      currentState     = TrafficState::GREEN;
      remainingSeconds = DURATION_GREEN_SEC;
      break;

    case TrafficState::GREEN:
      currentState     = TrafficState::YELLOW;
      remainingSeconds = DURATION_YELLOW_SEC;
      break;

    case TrafficState::YELLOW:
      currentState     = TrafficState::RED;
      remainingSeconds = DURATION_RED_SEC;
      break;
  }

  applyLedOutputs(currentState);
}

// ============================================================================
// 6. ARDUINO LIFECYCLE FUNCTIONS
// ============================================================================

void setup() {
  // 1. Initialize Serial UART0 over USB
  Serial.begin(SERIAL_BAUD_RATE);
  
  // Brief stabilization pause for the USB-UART bridge (CP2102 / CH340)
  delay(200);

  // 2. Configure GPIO pins as digital outputs
  pinMode(PIN_LED_RED, OUTPUT);
  pinMode(PIN_LED_YELLOW, OUTPUT);
  pinMode(PIN_LED_GREEN, OUTPUT);

  // 3. Force all LEDs into a known OFF state before starting the cycle
  digitalWrite(PIN_LED_RED, LOW);
  digitalWrite(PIN_LED_YELLOW, LOW);
  digitalWrite(PIN_LED_GREEN, LOW);

  // 4. Initialize state machine to RED
  currentState     = TrafficState::RED;
  remainingSeconds = DURATION_RED_SEC;
  applyLedOutputs(currentState);

  // 5. Anchor the non-blocking timer and emit the initial state immediately
  lastTickMillis = millis();
  transmitTelemetry(currentState, remainingSeconds);
}

void loop() {
  uint32_t currentMillis = millis();

  // Unsigned subtraction safely handles the ~49.7-day millis() rollover
  if (currentMillis - lastTickMillis >= TICK_INTERVAL_MS) {
    // Increment by exact interval to eliminate cumulative timing drift
    lastTickMillis += TICK_INTERVAL_MS;

    if (remainingSeconds > 1) {
      remainingSeconds--;
    } else {
      // Current state duration completed; transition to next signal
      advanceTrafficState();
    }

    // Broadcast updated state and countdown over USB Serial
    transmitTelemetry(currentState, remainingSeconds);
  }
}
