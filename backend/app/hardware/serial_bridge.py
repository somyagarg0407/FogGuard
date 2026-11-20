"""
Direct USB Serial Hardware Bridge for FogGuard.
Allows physical Arduino (Uno, Nano, Mega) connected via USB to stream
distance telemetry directly to the FastAPI backend and 3D HUD without an ESP32.

Supports both:
1. JSON-line format: {"traffic":"GREEN","sensors":[{"id":"S1","zone":"front_left","dist":45.2},...]}
2. Arduino Serial Monitor line-by-line format:
     Sensor 1: 45.20 cm
     Sensor 2: 120.30 cm
     Sensor 3: No Echo
     Sensor 4: 85.10 cm
     Sensor 5: 200.00 cm
     Sensor 6: 15.50 cm
"""
import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional, List, Dict

logger = logging.getLogger(__name__)

try:
    import serial
    import serial.tools.list_ports
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False
    logger.info("pyserial is not installed. Direct USB Serial bridge is inactive until installed.")

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


class SerialHardwareBridge:
    def __init__(self):
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._port: Optional[str] = None
        self._baudrate: int = 115200
        self._last_received_payload: Optional[dict] = None
        self._last_received_time: Optional[datetime] = None
        # Sensor buffer for line-by-line Arduino streams
        self._sensor_buffer: Dict[str, Optional[float]] = {}
        self._max_sensor_seen = 4

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def current_port(self) -> Optional[str]:
        return self._port

    def list_ports(self) -> List[Dict[str, str]]:
        """List available serial/COM ports on the host machine."""
        if not SERIAL_AVAILABLE:
            return []
        try:
            ports = serial.tools.list_ports.comports()
            return [
                {
                    "device": p.device,
                    "description": p.description,
                    "hwid": p.hwid,
                }
                for p in ports
            ]
        except Exception as e:
            logger.error(f"Error enumerating serial ports: {e}")
            return []

    async def start(self, port: Optional[str] = None, baudrate: int = 115200):
        """Start reading serial telemetry from the designated COM port."""
        if not SERIAL_AVAILABLE:
            raise RuntimeError("pyserial is not installed. Install it with: pip install pyserial")

        if self._running:
            await self.stop()

        if not port:
            available = self.list_ports()
            if not available:
                raise RuntimeError("No serial COM ports found. Connect your Arduino via USB.")
            arduino_ports = [
                p["device"] for p in available
                if any(k in p["description"].lower() for k in ["arduino", "ch340", "cp210", "ftdi", "usb serial"])
            ]
            port = arduino_ports[0] if arduino_ports else available[0]["device"]

        self._port = port
        self._baudrate = baudrate
        self._running = True
        self._sensor_buffer.clear()
        self._task = asyncio.create_task(self._reader_loop())
        logger.info(f"Direct Arduino USB Serial Bridge started on {port} @ {baudrate} baud")

    async def stop(self):
        """Stop the serial reader task."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._port = None
        logger.info("Direct Arduino USB Serial Bridge stopped")

    async def _reader_loop(self):
        """Background loop that reads lines from the serial port."""
        from app.database.db import AsyncSessionLocal
        from app.api.iot import process_telemetry
        from app.schemas.schemas import TelemetryPayload, SensorData, TrafficSignalData, TrafficState
        from app.hardware.source import hardware_source

        loop = asyncio.get_running_loop()

        import time

        while self._running:
            try:
                ser = await loop.run_in_executor(
                    None,
                    lambda: serial.Serial(self._port, self._baudrate, timeout=0.02)
                )
                logger.info(f"Connected to Arduino on {self._port} @ {self._baudrate} baud (low-latency non-blocking mode)")

                try:
                    while self._running:
                        line = await loop.run_in_executor(None, ser.readline)
                        if not line:
                            await asyncio.sleep(0.002)
                            continue

                        host_rx_ns = time.perf_counter_ns()
                        text = line.decode("utf-8", errors="ignore").strip()
                        if not text:
                            continue

                        payload_dict = self._process_incoming_line(text)
                        if payload_dict:
                            self._last_received_payload = payload_dict
                            self._last_received_time = datetime.now(timezone.utc)

                            sensors = [SensorData(**s) for s in payload_dict.get("sensors", [])]
                            traffic = None
                            if "traffic_signal" in payload_dict and payload_dict["traffic_signal"]:
                                traffic = TrafficSignalData(
                                    state=TrafficState(payload_dict["traffic_signal"].get("state", "GREEN")),
                                    duration_seconds=payload_dict["traffic_signal"].get("duration_seconds", 30)
                                )

                            payload = TelemetryPayload(
                                device_id="fogguard-arduino",
                                timestamp=datetime.now(timezone.utc),
                                seq=payload_dict.get("seq"),
                                uptime_ms=payload_dict.get("uptime_ms"),
                                host_rx_ns=host_rx_ns,
                                sensors=sensors,
                                traffic_signal=traffic
                            )

                            hardware_source.receive(payload)

                            from app.simulation.engine import simulation_engine
                            if simulation_engine.is_running:
                                await simulation_engine.stop()
                                logger.info("Stopped simulation engine: live serial hardware stream active")

                            async with AsyncSessionLocal() as session:
                                await process_telemetry(payload, session, source="hardware")

                finally:
                    await loop.run_in_executor(None, ser.close)

            except Exception as e:
                if not self._running:
                    break
                logger.warning(f"Serial port {self._port} error: {e}. Retrying in 2 seconds...")
                await asyncio.sleep(2.0)

    def _process_incoming_line(self, line: str) -> Optional[dict]:
        """
        Parses either:
        A. Full JSON-line: {"traffic":"GREEN","sensors":[...]}
        B. Line-by-line format from the Arduino code:
           'Sensor 1: 45.20 cm' ... 'Sensor 6: ...'
        """
        # A. JSON-line format
        if line.startswith("{") and line.endswith("}"):
            try:
                data = json.loads(line)
                sensors = []
                for s in data.get("sensors", []):
                    sid = s.get("id")
                    zone = s.get("zone") or ZONE_MAP_6.get(sid) or ZONE_MAP_4.get(sid, "front_center")
                    sensors.append({
                        "sensor_id": sid,
                        "zone": zone,
                        "distance_cm": s.get("dist"),
                        "obstacle_detected": s.get("det", False)
                    })
                traffic = None
                if "traffic" in data:
                    traffic = {
                        "state": data.get("traffic", "GREEN"),
                        "duration_seconds": data.get("dur", 30)
                    }
                elif data.get("module") == "traffic_signal":
                    traffic = {
                        "state": data.get("state", "RED"),
                        "duration_seconds": data.get("remaining_seconds", 5)
                    }
                return {
                    "sensors": sensors,
                    "traffic_signal": traffic,
                    "seq": data.get("seq"),
                    "uptime_ms": data.get("up") or data.get("uptime_ms"),
                }
            except Exception:
                pass

        # B. Line-by-line format: 'Sensor <index>: <distance> cm' OR 'Sensor <index>: No Echo'
        line_match = re.match(r"Sensor\s+([1-6])\s*:\s*(?:([0-9.]+)\s*cm|No Echo)", line, re.IGNORECASE)
        if line_match:
            idx = int(line_match.group(1))
            sensor_id = f"S{idx}"
            dist_val = float(line_match.group(2)) if line_match.group(2) else None

            # If a 4-sensor cycle completed and next S1 arrives, flush the 4-sensor payload
            if idx == 1 and len(self._sensor_buffer) >= 4 and all(int(k[1:]) <= 4 for k in self._sensor_buffer):
                sensors = []
                for i in range(1, 5):
                    sid = f"S{i}"
                    dist = self._sensor_buffer.get(sid)
                    detected = (dist is not None and dist <= 150.0)
                    sensors.append({
                        "sensor_id": sid,
                        "zone": ZONE_MAP_4[sid],
                        "distance_cm": dist,
                        "obstacle_detected": detected
                    })
                self._sensor_buffer.clear()
                self._sensor_buffer[sensor_id] = dist_val
                return {"sensors": sensors, "traffic_signal": {"state": "GREEN", "duration_seconds": 30}}

            self._sensor_buffer[sensor_id] = dist_val

            # When Sensor 6 arrives, flush the full 6-sensor payload
            if idx == 6 or len(self._sensor_buffer) >= 6:
                sensors = []
                for i in range(1, 7):
                    sid = f"S{i}"
                    dist = self._sensor_buffer.get(sid)
                    detected = (dist is not None and dist <= 150.0)
                    sensors.append({
                        "sensor_id": sid,
                        "zone": ZONE_MAP_6[sid],
                        "distance_cm": dist,
                        "obstacle_detected": detected
                    })
                self._sensor_buffer.clear()
                return {"sensors": sensors, "traffic_signal": {"state": "GREEN", "duration_seconds": 30}}

        return None


serial_bridge = SerialHardwareBridge()
