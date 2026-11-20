# FogGuard
(On Going)

Arduino-based ultrasonic sensor interface for tackling fog during winters in Delhi.

## Hardware

- Arduino Uno
- HC-SR04 Ultrasonic Sensors

## Sensor Configuration

Four ultrasonic sensors are planned for front-facing obstacle detection.

| Sensor | Position     | ECHO Pin |
| ------ | ------------ | -------- |
| S1     | Front-left   | D2       |
| S2     | Front-centre | D3       |
| S3     | Front-right  | D4       |
| S4     | Roof-centre  | D5       |

Proposed TRIG pin allocation: D8–D11.

## Implementation Approach

- Using Arduino Pin Change Interrupts to monitor ultrasonic ECHO signals.
- Using Pin Change Interrupt Group 2 (`PCINT2_vect`) for digital pins D2–D5.
- Using `PCICR` to enable the interrupt group.
- Using `PCMSK2` to select the pins being monitored.
- Using `PIND` to read the current pin states.
- Using XOR (`^`) and bit masks to identify pin-state changes.
- Detecting rising and falling ECHO edges.
- Using `micros()` to capture signal transition timestamps.

## Timestamp Storage

Two arrays are planned for storing the timestamps of four sensors:

```cpp
volatile unsigned long startTime[4] = {0, 0, 0, 0};
volatile unsigned long endTime[4] = {0, 0, 0, 0};
```

| Array Index | Sensor            |
| ----------- | ----------------- |
| 0           | S1 – Front-left   |
| 1           | S2 – Front-centre |
| 2           | S3 – Front-right  |
| 3           | S4 – Roof-centre  |

## Current Status

- Sensor placement and pin allocation discussed.
- Interrupt-based ECHO detection logic developed conceptually.
- Timestamp capture logic introduced for Sensor 1.
- Complete Arduino implementation and physical sensor testing are pending.

