# FogGuard System Architecture

## 1. Overview
**FogGuard** is an IoT-based fog-resistant obstacle detection and smart traffic management system designed for intelligent vehicular safety and municipal traffic control.

The system combines physical sensor telemetry from ultrasonic sensors and traffic signaling hardware with high-performance real-time processing and 3D web-based command visualization.

```
       +---------------------------------------------+
       |             PHYSICAL HARDWARE               |
       |  6x HC-SR04 Ultrasonic Sensors (S1-S6)     |
       |  3x Traffic LEDs (Red, Yellow, Green)       |
       +---------------------------------------------+
                              |
                              v (GPIO / Pulse Timing)
       +---------------------------------------------+
       |               ARDUINO MICRO                 |
       |  - High-frequency ultrasonic pulse timing   |
       |  - LED state-machine control & timing       |
       +---------------------------------------------+
                              |
                              v (UART @ 115200 baud)
       +---------------------------------------------+
       |               ESP32 GATEWAY                 |
       |  - Wi-Fi 802.11 b/g/n & NTP time sync       |
       |  - Bluetooth Serial local diagnostics       |
       |  - Formats validated JSON telemetry         |
       +---------------------------------------------+
                              |
                              v (HTTP POST / REST)
       +---------------------------------------------+
       |            FASTAPI BACKEND SERVICE          |
       |  - Telemetry validation & normalization     |
       |  - Deduplicated Warning Engine              |
       |  - SQLite + SQLAlchemy ORM persistence      |
       |  - WebSocket broadcast manager              |
       |  - Built-in multi-scenario Simulation Engine|
       +---------------------------------------------+
               /                             \
              v                               v
+-------------------------+     +-------------------------------+
|     SQLITE DATABASE     |     |       WEBSOCKET STREAM        |
| - Sensor readings       |     | - Real-time push updates      |
| - Obstacle events       |     | - Latency < 20ms              |
| - Warning events        |     +-------------------------------+
| - Traffic signal logs   |                     |
| - System config         |                     v
+-------------------------+     +-------------------------------+
                                |     REACT + THREE.JS UI       |
                                | - 3D Vehicle & Sensor Cone    |
                                | - Dynamic Cuboid Obstacles    |
                                | - Real-time Warning Cards     |
                                | - Analytics & History tables  |
                                +-------------------------------+
```

## 2. Sensor Zones & Spatial Mapping
The 6 ultrasonic sensors are mapped around the vehicle chassis as follows:

| Sensor ID | Zone Identifier | Spatial Position | Relative Angle |
|-----------|-----------------|------------------|----------------|
| **S1** | `front_left` | Front Bumper, Left Corner | -25 deg |
| **S2** | `front_center_left` | Front Bumper, Mid-Left | -8 deg |
| **S3** | `front_center_right` | Front Bumper, Mid-Right | +8 deg |
| **S4** | `front_right` | Front Bumper, Right Corner | +25 deg |
| **S5** | `left_side` | Driver Door Quarter-Panel | -90 deg |
| **S6** | `right_side` | Passenger Door Quarter-Panel | +90 deg |

## 3. Communication Pipelines

### A. Arduino to ESP32
- **Protocol**: Hardware UART Serial at 115200 baud (8N1).
- **Format**: Compact JSON-lines delimitered with newline (`\n`).

### B. ESP32 to FastAPI Backend
- **Protocol**: HTTP/1.1 REST POST.
- **Endpoint**: `/api/v1/iot/telemetry`
- **Security**: Can be fronted with API key or Bearer token header.

### C. Backend to React Frontend
- **Protocol**: HTML5 WebSockets.
- **Endpoint**: `ws://<host>:8000/ws`
- **Reconnection**: Automatic exponential backoff with ping/pong keepalive.
- **Payload**: Full state broadcast on changes and telemetry ingestion.

## 4. Dual Operating Modes
- **Hardware Mode**: Telemetry ingested from ESP32 via HTTP POST.
- **Simulation Mode**: Built-in Python simulation engine with 7 realistic scenarios (Normal, Single Obstacle, Multiple Obstacles, Critical Front, Side Obstacle, Dynamic Approaching, Dense Fog) producing normalized data through the identical backend processing pipeline.
