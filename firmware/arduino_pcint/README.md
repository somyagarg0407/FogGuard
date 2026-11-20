# FogGuard Interrupt-Driven (PCINT) Arduino Controller

This firmware module implements a **high-speed, non-blocking ultrasonic sensor and traffic signal controller** for FogGuard based on the Pin Change Interrupt architecture from [Vishwanath-aiml/FogGuard](https://github.com/Vishwanath-aiml/FogGuard.git).

---

## 1. Why Interrupt-Driven (PCINT) for Real-Time FogGuard?

Traditional ultrasonic firmware uses Arduino's `pulseIn(echoPin, HIGH)` function. However, `pulseIn()` is **blocking**:
- If a sensor times out (e.g. no obstacle detected up to 400 cm), `pulseIn()` halts the microcontroller for up to **30 ms per sensor**.
- In a 4 or 6 sensor array, multiple timeouts can block the main loop for **100–180 ms**, dropping the telemetry rate below 5 Hz and causing lag in the driver's HUD 3D cuboid projection.

### The Solution:
- Uses AVR **Pin Change Interrupt Group 2 (`PCINT2_vect`)** on ATmega328P Digital Pins **D2–D5**.
- Captures rising and falling ECHO pulses in microsecond timestamps (`micros()`) in hardware with **zero blocking**.
- A round-robin sequencer triggers each sensor sequentially (staggered by 25 ms to prevent acoustic crosstalk), allowing telemetry broadcasts at **10–15 Hz** consistently.
- Leaves the CPU free to handle the traffic light state machine and serial streaming simultaneously.

---

## 2. Directory Structure

- `fogguard_arduino_pcint/fogguard_arduino_pcint.ino`: Production-ready, fully combined firmware with fixed AVR registers, non-blocking sequencing, distance calculation, traffic signal controller, and JSON-line serial output for ESP32.
- `raw_github_source/`: Exact original code and files cloned from the GitHub repository (`https://github.com/Vishwanath-aiml/FogGuard.git`) for archival reference.

---

## 3. Hardware Configuration & Pinout

### A. Ultrasonic Sensors (HC-SR04) to Arduino Uno/Nano

All sensor VCC pins connect to **+5V**; all GND pins connect to **GND**.

| Sensor | Role / Zone | Trigger Pin | Echo Pin | AVR Pin / PCINT |
| :--- | :--- | :--- | :--- | :--- |
| **S1** | Front Left | Pin 9 | Pin 2 | PD2 (`PCINT18`) |
| **S2** | Front Center | Pin 10 | Pin 3 | PD3 (`PCINT19`) |
| **S3** | Front Right | Pin 11 | Pin 4 | PD4 (`PCINT20`) |
| **S4** | Roof Center | Pin 12 | Pin 5 | PD5 (`PCINT21`) |

### B. Traffic Signal LEDs to Arduino

Connect through 220 $\Omega$ current-limiting resistors to Arduino GND.

| Signal Color | Arduino Pin |
| :--- | :--- |
| **Red LED** | Analog Pin A0 |
| **Yellow LED** | Analog Pin A1 |
| **Green LED** | Analog Pin A2 |

### C. Arduino to ESP32 Gateway Serial Interface

| Arduino Pin | ESP32 Pin | Note |
| :--- | :--- | :--- |
| **TX (Pin 1)** | **RX2 (GPIO 16)** | Use 1k/2k voltage divider if 5V Arduino to 3.3V ESP32 |
| **RX (Pin 0)** | **TX2 (GPIO 17)** | Direct connection |
| **GND** | **GND** | Common ground is required |

---

## 4. Telemetry Format (to ESP32 @ 115200 Baud)

Outputs single-line compact JSON strings:

```json
{"traffic":"RED","dur":30,"sensors":[{"id":"S1","zone":"front_left","dist":45.2,"det":true},{"id":"S2","zone":"front_center","dist":112.4,"det":true},{"id":"S3","zone":"front_right","dist":null,"det":false},{"id":"S4","zone":"roof_center","dist":250.0,"det":false}]}
```

The ESP32 gateway receives this line over Serial2, attaches ISO 8601 UTC timestamps, and dispatches it via HTTP POST to `/api/v1/iot/telemetry`.

---

## 5. How to Flash

1. Open the Arduino IDE.
2. Open `fogguard_arduino_pcint/fogguard_arduino_pcint.ino`.
3. Select board: **Arduino Uno** or **Arduino Nano** (ATmega328P).
4. Select your COM Port and click **Upload**.
5. Open Serial Monitor at **115200 baud** to verify live JSON telemetry packets.
