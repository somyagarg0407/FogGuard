#!/usr/bin/env python3
"""
FogGuard Ultra-Low-Latency USB Serial Bridge CLI Tool.
Reads live distance telemetry from an Arduino connected via USB cable,
and pushes it to the FogGuard FastAPI backend (http://localhost:8000).

Optimizations:
1. Persistent HTTP keep-alive connection pool (requests.Session) — zero TCP handshake latency.
2. Low serial timeout (20 ms) — non-blocking serial line consumption.
3. High-resolution monotonic timing (host_rx_ns) and sequence tracking.
4. Supports canonical compact JSON-line format ({"seq":1024,"up":45120,...}) and line-by-line fallback.

Usage:
    python tools/arduino_serial_bridge.py [--port COM5] [--baud 115200] [--url http://localhost:8000/api/v1/iot/telemetry]
"""

import sys
import json
import re
import time
import argparse
from datetime import datetime, timezone

try:
    import serial
    import serial.tools.list_ports
    import requests
except ImportError:
    print("Please install requirements: pip install pyserial requests")
    sys.exit(1)

NUM_SENSORS = 4
DETECT_THRESHOLD_CM = 150.0

ZONE_MAP_6 = {
    "S1": "front_left",
    "S2": "front_center_left",
    "S3": "front_center_right",
    "S4": "front_right",
    "S5": "left_side",
    "S6": "right_side",
}

ZONE_MAP_4 = {
    "S1": "front_left",
    "S2": "front_center",
    "S3": "front_right",
    "S4": "roof_center",
}

SENSOR_RE = re.compile(
    r"Sensor\s+([1-6])\s*:\s*(?:([0-9.]+)\s*cm|No Echo)", re.IGNORECASE
)

sensor_buffer = {}


def find_arduino_port():
    ports = serial.tools.list_ports.comports()
    if not ports:
        return None
    for p in ports:
        desc = (p.description or "").lower()
        if any(k in desc for k in ["arduino", "ch340", "cp210", "ftdi", "usb serial"]):
            return p.device
    return ports[0].device


def parse_line(line: str):
    global sensor_buffer
    line = line.strip()
    if not line:
        return None

    # Format 1: full JSON line (Canonical firmware)
    if line.startswith("{") and line.endswith("}"):
        try:
            data = json.loads(line)
            sensors = []
            raw_sensors = data.get("sensors", [])
            active_zones = ZONE_MAP_4 if len(raw_sensors) <= 4 else ZONE_MAP_6
            for s in raw_sensors:
                sid = s.get("id")
                zone = s.get("zone") or active_zones.get(sid, "front_center")
                dist = s.get("dist")
                det = s.get("det", (dist is not None and dist <= DETECT_THRESHOLD_CM))
                sensors.append({
                    "id": sid,
                    "zone": zone,
                    "dist": dist,
                    "det": det,
                })
            traffic_state = data.get("traffic")
            dur = data.get("dur", 30)
            if data.get("module") == "traffic_signal":
                traffic_state = data.get("state")
                dur = data.get("remaining_seconds", 5)

            return {
                "sensors": sensors,
                "seq": data.get("seq"),
                "uptime_ms": data.get("up") or data.get("uptime_ms"),
                "traffic": traffic_state,
                "dur": dur,
            }
        except Exception:
            pass

    # Format 2: 'Sensor <n>: <distance> cm' or 'Sensor <n>: No Echo'
    m = SENSOR_RE.match(line)
    if not m:
        return None

    idx = int(m.group(1))
    if idx == 1:
        sensor_buffer = {}  # new sweep starts: drop any leftovers
    sensor_buffer[f"S{idx}"] = float(m.group(2)) if m.group(2) else None

    # # 4-sensor sweep completion check
    # if idx == 4 and NUM_SENSORS == 4:
    #     sensors = []
    #     for i in range(1, 5):
    #         sid = f"S{i}"
    #         dist = sensor_buffer.get(sid)
    #         sensors.append({
    #             "id": sid,
    #             "zone": ZONE_MAP_4[sid],
    #             "dist": dist,
    #             "det": (dist is not None and dist <= DETECT_THRESHOLD_CM),
    #         })
    #     sensor_buffer = {}
    #     return {"sensors": sensors}

    # 6-sensor sweep completion check
    if idx == 6 or len(sensor_buffer) >= 6:
        sensors = []
        for i in range(1, 7):
            sid = f"S{i}"
            dist = sensor_buffer.get(sid)
            sensors.append({
                "id": sid,
                "zone": ZONE_MAP_6[sid],
                "dist": dist,
                "det": (dist is not None and dist <= DETECT_THRESHOLD_CM),
            })
        sensor_buffer = {}
        return {"sensors": sensors}

    return None


def main():
    global NUM_SENSORS
    parser = argparse.ArgumentParser(description="FogGuard High-Speed USB Serial Bridge")
    parser.add_argument("--port", type=str, default=None, help="COM / tty port (default: auto-detect)")
    parser.add_argument("--baud", type=int, default=115200, help="Baud rate (default: 115200)")
    parser.add_argument("--url", type=str, default="http://localhost:8000/api/v1/iot/telemetry", help="Backend telemetry endpoint")
    parser.add_argument("--sensors", type=int, default=4, choices=[4, 6], help="Number of sensors (4 or 6)")
    args = parser.parse_args()

    NUM_SENSORS = args.sensors
    port = args.port or find_arduino_port()
    if not port:
        print("[ERROR] No USB serial ports detected. Please plug in your Arduino and try again.")
        sys.exit(1)

    print(f"[FogGuard] Connecting to Arduino on {port} @ {args.baud} baud (low-latency mode)...")
    try:
        # Bounded 20ms timeout prevents blocking the thread
        ser = serial.Serial(port, args.baud, timeout=0.02)
    except Exception as e:
        print(f"[ERROR] Could not open serial port {port}: {e}")
        sys.exit(1)

    # Persistent HTTP Session with keep-alive connection pooling
    session = requests.Session()
    adapter = requests.adapters.HTTPAdapter(pool_connections=1, pool_maxsize=1, max_retries=0)
    session.mount("http://", adapter)

    print(f"[FogGuard] Connected! High-rate telemetry streaming to {args.url}")
    print(f"[FogGuard] Configured for {NUM_SENSORS} sensors @ {args.baud} baud.")
    print("[FogGuard] Press Ctrl+C to stop.\n")

    frame_count = 0
    t0 = time.time()

    try:
        while True:
            try:
                raw_line = ser.readline()
            except serial.SerialException as e:
                print(f"[ERROR] Serial connection lost: {e}")
                break

            if not raw_line:
                time.sleep(0.002)
                continue

            host_rx_ns = time.perf_counter_ns()
            text = raw_line.decode("utf-8", errors="ignore").strip()
            data = parse_line(text)
            if not data or "sensors" not in data:
                continue

            frame_count += 1
            payload = {
                "device_id": "fogguard-arduino",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "seq": data.get("seq", frame_count),
                "uptime_ms": data.get("uptime_ms"),
                "host_rx_ns": host_rx_ns,
                "sensors": [
                    {
                        "sensor_id": s.get("id"),
                        "zone": s.get("zone", "front_center"),
                        "distance_cm": s.get("dist"),
                        "obstacle_detected": s.get("det", False),
                    }
                    for s in data["sensors"]
                ],
                "traffic_signal": {
                    "state": data.get("traffic", "GREEN"),
                    "duration_seconds": data.get("dur", 30),
                } if data.get("traffic") else None,
            }

            try:
                resp = session.post(args.url, json=payload, timeout=0.5)
                if resp.status_code == 200:
                    now = time.time()
                    elapsed = now - t0
                    if elapsed >= 1.0:
                        fps = frame_count / elapsed
                        dists = [
                            f"{s['sensor_id']}={s['distance_cm']:.1f}cm"
                            for s in payload["sensors"]
                            if s["distance_cm"] is not None
                        ]
                        print(f"[{datetime.now().strftime('%H:%M:%S')}] Rate: {fps:.1f} Hz | Frame #{payload['seq']} | {', '.join(dists) if dists else 'All Clear'}")
                        frame_count = 0
                        t0 = now
                else:
                    print(f"[WARN] Backend responded with HTTP {resp.status_code}: {resp.text[:200]}")
            except Exception as e:
                print(f"[WARN] Telemetry push error: {e}")

    except KeyboardInterrupt:
        print("\n[FogGuard] Bridge stopped cleanly.")
    finally:
        ser.close()
        session.close()


if __name__ == "__main__":
    main()
