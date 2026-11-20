# FogGuard Hardware Integration Guide

This document explains how to wire, configure, flash, and connect the physical Arduino and ESP32 hardware to the FogGuard software system.

---

## 1. Hardware Bill of Materials (BOM)
- 1x Arduino (Uno, Mega, or Nano)
- 1x ESP32 Dev Board (Wi-Fi + Bluetooth enabled)
- 6x HC-SR04 Ultrasonic Sensors
- 3x LEDs (1 Red, 1 Yellow, 1 Green)
- 3x 220 Ohm Resistors (for LEDs)
- Breadboard & Jumper Wires
- 5V Power Supply / USB cables

---

## 2. Pin Wiring & Schematics

### A. Ultrasonic Sensors to Arduino

FogGuard supports two firmware modes depending on your hardware requirements:

#### Option 1: 6-Sensor Standard Polling Mode (`firmware/arduino/fogguard_arduino/`)
Best for full 360-degree perimeter coverage around the vehicle. All VCC pins connect to +5V; all GND pins connect to GND.

| Sensor | Role / Zone | Trigger Pin | Echo Pin |
|--------|-------------|-------------|----------|
| **S1** | Front Left | Pin 2 | Pin 3 |
| **S2** | Front Center Left | Pin 4 | Pin 5 |
| **S3** | Front Center Right | Pin 6 | Pin 7 |
| **S4** | Front Right | Pin 8 | Pin 9 |
| **S5** | Left Side | Pin 10 | Pin 11 |
| **S6** | Right Side | Pin 12 | Pin 13 |

#### Option 2: 4-Sensor Real-Time Interrupt (PCINT) Mode (`firmware/arduino_pcint/fogguard_arduino_pcint/`)
*Recommended for low-latency real-time 3D HUD projection.* Uses AVR Pin Change Interrupts (`PCINT2_vect`) on Port D for zero-blocking ECHO pulse capture and up to 15 Hz refresh rate.

| Sensor | Role / Zone | Trigger Pin | Echo Pin | AVR Vector |
|--------|-------------|-------------|----------|------------|
| **S1** | Front Left | Pin 9 | Pin 2 | PD2 (`PCINT18`) |
| **S2** | Front Center | Pin 10 | Pin 3 | PD3 (`PCINT19`) |
| **S3** | Front Right | Pin 11 | Pin 4 | PD4 (`PCINT20`) |
| **S4** | Roof Center | Pin 12 | Pin 5 | PD5 (`PCINT21`) |

### B. Traffic Signal LEDs to Arduino
Cathodes connect to Arduino GND via 220 Ohm current-limiting resistors.

| Signal Color | Arduino Pin |
|--------------|-------------|
| **Red LED** | Pin A0 |
| **Yellow LED** | Pin A1 |
| **Green LED** | Pin A2 |

### C. Arduino to ESP32 Serial Interface
Connect Arduino Serial TX/RX to ESP32 Hardware Serial 2:
- **Arduino TX (Pin 1)** -> **ESP32 RX2 (GPIO 16)** *(Use a 1k/2k voltage divider if your Arduino is 5V logic and ESP32 is 3.3V)*
- **Arduino RX (Pin 0)** <- **ESP32 TX2 (GPIO 17)**
- **Common Ground**: Connect Arduino GND directly to ESP32 GND.

---

## 3. Firmware Flashing Instructions

### A. Arduino Firmware
Choose one of the two Arduino firmware sketches:
- **For 4-Sensor High-Speed Interrupt (PCINT) Mode**: Open `firmware/arduino_pcint/fogguard_arduino_pcint/fogguard_arduino_pcint.ino`.
- **For 6-Sensor Standard Polling Mode**: Open `firmware/arduino/fogguard_arduino/fogguard_arduino.ino`.

1. Select your board (e.g., Arduino Uno or Nano) and correct COM port.
2. Click **Upload**.
3. Once uploaded, the traffic light state machine will begin cycling immediately and ultrasonic telemetry packets will begin transmitting over Serial at 115200 baud.

### B. ESP32 Firmware
1. Open `firmware/esp32/fogguard_esp32.ino` in the Arduino IDE.
2. In the code, configure your Wi-Fi credentials and FogGuard Backend IP address:
   ```cpp
   const char* WIFI_SSID     = "YOUR_WIFI_SSID";
   const char* WIFI_PASSWORD = "YOUR_WIFI_PASSWORD";
   const char* SERVER_URL    = "http://<YOUR_BACKEND_IP>:8000/api/v1/iot/telemetry";
   ```
3. Install required libraries in the Arduino IDE Library Manager:
   - `ArduinoJson` (v6 or v7)
4. Select board **ESP32 Dev Module** and the correct COM port.
5. Click **Upload**.
6. When the onboard LED turns solid blue/green, the ESP32 is connected to Wi-Fi and actively posting telemetry to the backend.

---

## 4. Hardware Verification & Troubleshooting
1. **Bluetooth Diagnostics**: Connect a smartphone or laptop to the Bluetooth serial device named `FogGuard-Gateway` using any Serial Terminal app (e.g. Serial Bluetooth Terminal on Android). You will see real-time JSON payloads being dispatched.
2. **Dashboard Verification**:
   - Open `http://localhost:5173/devices`.
   - The device status will switch from `SIMULATED` to `CONNECTED` with a live heartbeat timestamp.
   - The main header badge will switch from `SIMULATION` to `HARDWARE`.
