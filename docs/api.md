# FogGuard REST & WebSocket API Documentation

Base URL: `http://localhost:8000/api/v1`  
Interactive OpenAPI Swagger Docs: `http://localhost:8000/docs`  
ReDoc: `http://localhost:8000/redoc`

---

## 1. IoT Telemetry & Ingestion

### `POST /api/v1/iot/telemetry`
Receives live telemetry payload from ESP32 hardware or simulation runner.

**Request Payload:**
```json
{
  "device_id": "fogguard-esp32",
  "timestamp": "2026-11-14T10:00:00Z",
  "sensors": [
    {
      "sensor_id": "S1",
      "zone": "front_left",
      "distance_cm": 45.2,
      "obstacle_detected": true
    },
    {
      "sensor_id": "S2",
      "zone": "front_center_left",
      "distance_cm": 120.0,
      "obstacle_detected": true
    },
    {
      "sensor_id": "S3",
      "zone": "front_center_right",
      "distance_cm": 200.0,
      "obstacle_detected": false
    },
    {
      "sensor_id": "S4",
      "zone": "front_right",
      "distance_cm": 250.0,
      "obstacle_detected": false
    },
    {
      "sensor_id": "S5",
      "zone": "left_side",
      "distance_cm": 80.0,
      "obstacle_detected": true
    },
    {
      "sensor_id": "S6",
      "zone": "right_side",
      "distance_cm": 180.0,
      "obstacle_detected": false
    }
  ],
  "traffic_signal": {
    "state": "GREEN",
    "duration_seconds": 25
  }
}
```

**Response (200 OK):**
```json
{
  "status": "ok",
  "processed_sensors": 6
}
```

---

## 2. Simulation Engine

### `POST /api/v1/simulation/control`
Controls the background simulation engine.

**Request Body:**
```json
{
  "action": "start",
  "scenario": "dense_fog",
  "speed_multiplier": 1.0
}
```
*Actions:* `start`, `stop`, `reset`.  
*Scenarios:* `normal`, `single_obstacle`, `multiple_obstacles`, `critical_front`, `side_obstacle`, `dynamic_approaching`, `dense_fog`.

### `GET /api/v1/simulation/status`
Returns current simulation state.

### `GET /api/v1/simulation/scenarios`
Returns list of available simulation scenarios with descriptions.

---

## 3. Sensors & Obstacles

### `GET /api/v1/sensors/latest`
Returns the most recently recorded telemetry reading.

### `GET /api/v1/sensors/history?sensor_id=S1&limit=50&offset=0`
Returns historical raw readings.

### `GET /api/v1/obstacles?sensor_id=S1&zone=front_left&severity=CRITICAL&limit=50`
Queries recorded obstacle detection events.

---

## 4. Warnings & Alerts

### `GET /api/v1/warnings?warning_level=CRITICAL&acknowledged=false&limit=50`
Returns active or historical warnings.

### `POST /api/v1/warnings/acknowledge`
Acknowledges a specific warning by ID.
```json
{ "warning_id": 42 }
```

### `POST /api/v1/warnings/acknowledge-all`
Marks all existing unacknowledged warnings as acknowledged.

---

## 5. Traffic Signal

### `GET /api/v1/traffic/status`
Returns active traffic signal state and countdown duration.

### `GET /api/v1/traffic/history?limit=50`
Returns historical traffic signal state changes.

---

## 6. Analytics

### `GET /api/v1/analytics/summary`
Returns aggregate statistics: total detections, warnings count, critical count, most frequent zone, min obstacle distance.

### `GET /api/v1/analytics/obstacles-over-time`
Time-series distribution of obstacle detections.

### `GET /api/v1/analytics/warnings-over-time`
Time-series distribution grouped by warning severity.

### `GET /api/v1/analytics/traffic-distribution`
Total counts for RED, YELLOW, and GREEN signal states.

### `GET /api/v1/analytics/sensor-heatmap`
Matrix of detection counts per sensor and severity level.

---

## 7. Device Status & Settings

### `GET /api/v1/devices/status`
Returns connection status and last-seen timestamps for Arduino, ESP32, and all 6 ultrasonic sensors.

### `GET /api/v1/devices/system-info`
System health, current operational mode, threshold configuration.

### `GET /api/v1/settings/thresholds`
Fetches current distance threshold configuration.

### `POST /api/v1/settings/thresholds`
Updates and persists distance thresholds into SQLite.
```json
{
  "critical_cm": 50.0,
  "warning_cm": 100.0,
  "caution_cm": 150.0,
  "max_range_cm": 400.0
}
```

### `POST /api/v1/settings/cleanup?retention_days=30`
Purges raw high-frequency sensor readings older than `retention_days`.

---

## 8. WebSocket Stream

### `ws://localhost:8000/ws`
Real-time full-duplex stream.
- On connection, client receives the latest system snapshot immediately.
- Broadcasts every incoming telemetry frame, state change, and new warning event.
