/*
 * ==============================================================================
 * Project: FogGuard — IoT Obstacle Detection & Traffic Management System
 * Module: ESP32 Wi-Fi & Gateway Controller
 * Target: ESP32 Dev Module
 * 
 * Hardware Configuration:
 * - UART2 connected to Arduino:
 *   - ESP32 Pin 16 (RX2) <- Arduino TX
 *   - ESP32 Pin 17 (TX2) -> Arduino RX
 * - Onboard LED: GPIO 2 (Status Indicator)
 * - Traffic LEDs: Red GPIO 25, Yellow GPIO 33, Green GPIO 32
 *   - Note: GPIO 34-39 are input-only on ESP32-WROOM and cannot drive LEDs.
 *   - GPIO 25, 33, and 32 are full bidirectional output-capable pins.
 * 
 * Functional Responsibilities:
 * 1. Connects to Wi-Fi network with persistent auto-reconnect.
 * 2. Reads structured sensor & traffic packets from Arduino over Serial2.
 * 3. Enriches telemetry with device ID and ISO 8601 UTC timestamp.
 * 4. Dispatches POST /api/v1/iot/telemetry payloads to FastAPI backend.
 * 5. Provides Bluetooth Serial diagnostics interface.
 * ==============================================================================
 */

#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include <BluetoothSerial.h>
#include <time.h>

// ─── User Network Configuration ──────────────────────────────────────────────
const char* WIFI_SSID     = "YOUR_WIFI_SSID";
const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";

// FogGuard Backend Server URL
const char* SERVER_URL    = "http://192.168.1.100:8000/api/v1/iot/telemetry";
const char* DEVICE_ID     = "fogguard-esp32";

// Hardware Serial2 pins for Arduino communication
#define RXD2 16
#define TXD2 17

// Status LED
#define STATUS_LED 2

// Traffic signal LEDs (Red=25, Yellow=33, Green=32)
#define TRAFFIC_RED_LED 25
#define TRAFFIC_YELLOW_LED 33
#define TRAFFIC_GREEN_LED 32

// NTP Server Settings for UTC timestamping
const char* NTP_SERVER = "pool.ntp.org";
const long  GMT_OFFSET_SEC = 0;
const int   DAYLIGHT_OFFSET_SEC = 0;

// Bluetooth Serial for diagnostics
BluetoothSerial SerialBT;
bool enableBluetooth = true;

void setTrafficLedState(const char* state) {
  digitalWrite(TRAFFIC_RED_LED, LOW);
  digitalWrite(TRAFFIC_YELLOW_LED, LOW);
  digitalWrite(TRAFFIC_GREEN_LED, LOW);

  if (strcmp(state, "RED") == 0) {
    digitalWrite(TRAFFIC_RED_LED, HIGH);
  } else if (strcmp(state, "YELLOW") == 0) {
    digitalWrite(TRAFFIC_YELLOW_LED, HIGH);
  } else if (strcmp(state, "GREEN") == 0) {
    digitalWrite(TRAFFIC_GREEN_LED, HIGH);
  }
}

// Timing variables
unsigned long lastHeartbeatTime = 0;
const unsigned long HEARTBEAT_INTERVAL_MS = 5000;

// Returns current ISO 8601 UTC timestamp string
String getISO8601Timestamp() {
  struct tm timeinfo;
  if (!getLocalTime(&timeinfo)) {
    return ""; // NTP time not yet synced
  }
  char buffer[32];
  strftime(buffer, sizeof(buffer), "%Y-%m-%dT%H:%M:%SZ", &timeinfo);
  return String(buffer);
}

void connectWiFi() {
  if (WiFi.status() == WL_CONNECTED) return;

  Serial.println("[FogGuard ESP32] Connecting to Wi-Fi...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    digitalWrite(STATUS_LED, !digitalRead(STATUS_LED)); // Blink while connecting
    Serial.print(".");
    attempts++;
  }

  if (WiFi.status() == WL_CONNECTED) {
    digitalWrite(STATUS_LED, HIGH);
    Serial.println("\n[FogGuard ESP32] Wi-Fi Connected!");
    Serial.print("[FogGuard ESP32] IP Address: ");
    Serial.println(WiFi.localIP());

    // Configure NTP time
    configTime(GMT_OFFSET_SEC, DAYLIGHT_OFFSET_SEC, NTP_SERVER);
  } else {
    digitalWrite(STATUS_LED, LOW);
    Serial.println("\n[FogGuard ESP32] Wi-Fi Connection Failed. Will retry in loop.");
  }
}

// Post telemetry JSON payload to FastAPI backend
bool sendTelemetry(const String& jsonPayload) {
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
    if (WiFi.status() != WL_CONNECTED) return false;
  }

  HTTPClient http;
  http.begin(SERVER_URL);
  http.addHeader("Content-Type", "application/json");
  http.setTimeout(4000); // 4-second timeout

  int httpCode = http.POST(jsonPayload);
  bool success = false;

  if (httpCode > 0) {
    if (httpCode == HTTP_CODE_OK || httpCode == HTTP_CODE_CREATED) {
      success = true;
    } else {
      Serial.printf("[FogGuard ESP32] HTTP POST returned code: %d\n", httpCode);
    }
  } else {
    Serial.printf("[FogGuard ESP32] HTTP POST failed, error: %s\n", http.errorToString(httpCode).c_str());
  }

  http.end();
  return success;
}

void setup() {
  Serial.begin(115200);
  Serial2.begin(115200, SERIAL_8N1, RXD2, TXD2);

  pinMode(STATUS_LED, OUTPUT);
  digitalWrite(STATUS_LED, LOW);

  pinMode(TRAFFIC_RED_LED, OUTPUT);
  pinMode(TRAFFIC_YELLOW_LED, OUTPUT);
  pinMode(TRAFFIC_GREEN_LED, OUTPUT);
  digitalWrite(TRAFFIC_RED_LED, LOW);
  digitalWrite(TRAFFIC_YELLOW_LED, LOW);

  // Initialize Bluetooth Serial for local diagnostics
  if (enableBluetooth) {
    SerialBT.begin("FogGuard-Gateway");
    Serial.println("[FogGuard ESP32] Bluetooth Diagnostics Initialized (FogGuard-Gateway)");
  }

  connectWiFi();
}

void loop() {
  // Ensure Wi-Fi remains connected
  if (WiFi.status() != WL_CONNECTED) {
    connectWiFi();
  }

  // Check for incoming packets from Arduino via Serial2
  if (Serial2.available()) {
    String incoming = Serial2.readStringUntil('\n');
    incoming.trim();

    if (incoming.length() > 0 && incoming.startsWith("{") && incoming.endsWith("}")) {
      // Parse Arduino packet
      DynamicJsonDocument docIn(1024);
      DeserializationError err = deserializeJson(docIn, incoming);

      if (!err) {
        // Construct standard FogGuard Telemetry Payload
        DynamicJsonDocument docOut(2048);
        docOut["device_id"] = DEVICE_ID;

        String ts = getISO8601Timestamp();
        if (ts.length() > 0) {
          docOut["timestamp"] = ts;
        }

        JsonArray sensorsOut = docOut.createNestedArray("sensors");
        JsonArray sensorsIn = docIn["sensors"];

        for (JsonObject s : sensorsIn) {
          JsonObject sensorObj = sensorsOut.createNestedObject();
          sensorObj["sensor_id"] = s["id"];
          sensorObj["zone"] = s["zone"];
          if (s["dist"].isNull()) {
            sensorObj["distance_cm"] = nullptr;
          } else {
            sensorObj["distance_cm"] = s["dist"].as<float>();
          }
          sensorObj["obstacle_detected"] = s["det"].as<bool>();
        }

        if (docIn.containsKey("traffic")) {
          const char* trafficState = docIn["traffic"].as<const char*>();
          JsonObject trafficObj = docOut.createNestedObject("traffic_signal");
          trafficObj["state"] = trafficState;
          trafficObj["duration_seconds"] = docIn["dur"].as<int>();
          setTrafficLedState(trafficState);
        }

        String outputPayload;
        serializeJson(docOut, outputPayload);

        // Send to backend
        bool ok = sendTelemetry(outputPayload);

        // Diagnostic outputs
        if (enableBluetooth && SerialBT.hasClient()) {
          SerialBT.println(outputPayload);
        }

        if (ok) {
          digitalWrite(STATUS_LED, HIGH);
        } else {
          // Short blink to signify dispatch error
          digitalWrite(STATUS_LED, LOW);
          delay(50);
          digitalWrite(STATUS_LED, HIGH);
        }
      } else {
        Serial.printf("[FogGuard ESP32] JSON parse error from Arduino: %s\n", err.c_str());
      }
    }
  }

  delay(20);
}
