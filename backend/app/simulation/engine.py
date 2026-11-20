"""
Simulation engine — generates realistic sensor data for demonstration.
Runs as a background asyncio task.
"""
import asyncio
import random
import math
import time
from datetime import datetime, timezone
from typing import Optional
import logging

from app.schemas.schemas import TelemetryPayload, SensorData, TrafficSignalData, TrafficState
from app.core.config import settings

logger = logging.getLogger(__name__)

SENSOR_ZONES = {
    "S1": "front_left",
    "S2": "front_center_left",
    "S3": "front_center_right",
    "S4": "front_right",
    "S5": "left_side",
    "S6": "right_side",
}

TRAFFIC_CYCLE = ["RED", "GREEN", "YELLOW"]
TRAFFIC_DURATIONS = {"RED": 30, "GREEN": 25, "YELLOW": 5}


class SimulationScenario:
    """Defines obstacle behavior for a scenario."""

    def __init__(self, name: str):
        self.name = name
        self._tick = 0
        self._traffic_state = "RED"
        self._traffic_elapsed = 0
        self._traffic_index = 0

    def next_traffic_state(self, delta_sec: float = 0.1):
        dur = TRAFFIC_DURATIONS[TRAFFIC_CYCLE[self._traffic_index]]
        self._traffic_elapsed += delta_sec
        if self._traffic_elapsed >= dur:
            self._traffic_elapsed = 0
            self._traffic_index = (self._traffic_index + 1) % len(TRAFFIC_CYCLE)
        return TRAFFIC_CYCLE[self._traffic_index], TRAFFIC_DURATIONS[TRAFFIC_CYCLE[self._traffic_index]]

    def get_readings(self, delta_sec: float = 0.1) -> dict:
        self._tick += 1
        t = self._tick
        state, dur = self.next_traffic_state(delta_sec)
        base = self._base_distances(t)
        return {
            "distances": base,
            "traffic_state": state,
            "traffic_duration": dur,
        }

    def _base_distances(self, t: int) -> dict:
        """Override in subclasses."""
        return {sid: None for sid in SENSOR_ZONES}


class NormalScenario(SimulationScenario):
    def _base_distances(self, t):
        # All clear, occasional distant readings
        return {
            "S1": random.uniform(200, 400),
            "S2": random.uniform(200, 400),
            "S3": random.uniform(200, 400),
            "S4": random.uniform(200, 400),
            "S5": random.uniform(200, 400),
            "S6": random.uniform(200, 400),
        }


class SingleObstacleAheadScenario(SimulationScenario):
    def _base_distances(self, t):
        dist = 160 + 40 * math.sin(t * 0.05)
        return {
            "S1": random.uniform(200, 400),
            "S2": dist + random.uniform(-5, 5),
            "S3": dist + random.uniform(-5, 5),
            "S4": random.uniform(200, 400),
            "S5": random.uniform(200, 400),
            "S6": random.uniform(200, 400),
        }


class MultipleObstaclesScenario(SimulationScenario):
    def _base_distances(self, t):
        return {
            "S1": 90 + 10 * math.sin(t * 0.07),
            "S2": 130 + 15 * math.sin(t * 0.05),
            "S3": 55 + 10 * math.sin(t * 0.06),
            "S4": random.uniform(200, 400),
            "S5": 85 + 8 * math.sin(t * 0.08),
            "S6": random.uniform(200, 400),
        }


class CriticalFrontObstacleScenario(SimulationScenario):
    def _base_distances(self, t):
        # Obstacle approaching from front
        dist = max(20, 200 - t * 2 if t < 90 else 20 + (t - 90) * 2)
        return {
            "S1": dist + random.uniform(-3, 3),
            "S2": dist * 0.9 + random.uniform(-3, 3),
            "S3": dist * 0.9 + random.uniform(-3, 3),
            "S4": dist + random.uniform(-3, 3),
            "S5": random.uniform(200, 400),
            "S6": random.uniform(200, 400),
        }


class SideObstacleScenario(SimulationScenario):
    def _base_distances(self, t):
        side = 60 + 20 * math.sin(t * 0.1)
        return {
            "S1": random.uniform(200, 400),
            "S2": random.uniform(200, 400),
            "S3": random.uniform(200, 400),
            "S4": random.uniform(200, 400),
            "S5": side + random.uniform(-5, 5),
            "S6": random.uniform(200, 400),
        }


class DynamicApproachingScenario(SimulationScenario):
    def __init__(self, name):
        super().__init__(name)
        self._dist = 400.0
        self._speed = random.uniform(3, 8)
        self._target_sensor = "S2"

    def _base_distances(self, t):
        self._dist = max(15, self._dist - self._speed)
        if self._dist <= 15:
            self._dist = 400.0
            self._speed = random.uniform(3, 8)
            self._target_sensor = random.choice(list(SENSOR_ZONES.keys()))
        result = {sid: random.uniform(200, 400) for sid in SENSOR_ZONES}
        result[self._target_sensor] = self._dist + random.uniform(-3, 3)
        return result


class DenseFogScenario(SimulationScenario):
    """Simulates dense fog — short random reads across all sensors."""
    def _base_distances(self, t):
        return {
            "S1": random.uniform(30, 120),
            "S2": random.uniform(30, 100),
            "S3": random.uniform(30, 100),
            "S4": random.uniform(30, 120),
            "S5": random.uniform(30, 80),
            "S6": random.uniform(30, 80),
        }


SCENARIOS = {
    "normal": NormalScenario,
    "single_obstacle": SingleObstacleAheadScenario,
    "multiple_obstacles": MultipleObstaclesScenario,
    "critical_front": CriticalFrontObstacleScenario,
    "side_obstacle": SideObstacleScenario,
    "dynamic_approaching": DynamicApproachingScenario,
    "dense_fog": DenseFogScenario,
}


class SimulationEngine:
    def __init__(self):
        self._running = False
        self._scenario_name = "normal"
        self._scenario: Optional[SimulationScenario] = None
        self._speed_multiplier = 1.0
        self._task: Optional[asyncio.Task] = None
        self._data_callback = None
        self._seq = 0
        self._start_time = 0.0

    def set_data_callback(self, callback):
        self._data_callback = callback

    async def start(self, scenario: str = "normal", speed: float = 1.0):
        if self._running:
            await self.stop()
        self._scenario_name = scenario
        self._speed_multiplier = max(0.1, min(speed, 10.0))
        cls = SCENARIOS.get(scenario, NormalScenario)
        self._scenario = cls(scenario)
        self._running = True
        self._seq = 0
        self._start_time = time.time()
        self._task = asyncio.create_task(self._run())
        logger.info(f"Simulation started: scenario={scenario}, speed={speed}x, interval={settings.SIMULATION_INTERVAL_MS}ms")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Simulation stopped")

    def reset(self):
        cls = SCENARIOS.get(self._scenario_name, NormalScenario)
        self._scenario = cls(self._scenario_name)
        self._seq = 0
        self._start_time = time.time()
        logger.info("Simulation reset")

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def scenario_name(self) -> str:
        return self._scenario_name

    async def _run(self):
        interval = settings.SIMULATION_INTERVAL_MS / 1000.0
        while self._running:
            try:
                payload = self._generate_payload(interval)
                if self._data_callback:
                    await self._data_callback(payload)
            except Exception as e:
                logger.error(f"Simulation error: {e}")
            await asyncio.sleep(interval / self._speed_multiplier)

    def _generate_payload(self, interval: float = 0.1) -> TelemetryPayload:
        self._seq += 1
        now_time = time.time()
        uptime_ms = int((now_time - self._start_time) * 1000)
        host_rx_ns = time.perf_counter_ns()

        data = self._scenario.get_readings(delta_sec=interval * self._speed_multiplier)
        sensors = []
        for sid, zone in SENSOR_ZONES.items():
            dist = data["distances"].get(sid)
            # Clamp and validate
            if dist is not None:
                dist = round(max(0, min(dist, settings.MAX_RANGE_CM)), 1)
            detected = dist is not None and dist <= settings.CAUTION_THRESHOLD_CM
            sensors.append(SensorData(
                sensor_id=sid,
                zone=zone,
                distance_cm=dist,
                obstacle_detected=detected,
            ))

        traffic = TrafficSignalData(
            state=TrafficState(data["traffic_state"]),
            duration_seconds=data["traffic_duration"],
        )

        return TelemetryPayload(
            device_id="fogguard-simulation",
            timestamp=datetime.now(timezone.utc),
            seq=self._seq,
            uptime_ms=uptime_ms,
            host_rx_ns=host_rx_ns,
            sensors=sensors,
            traffic_signal=traffic,
        )


simulation_engine = SimulationEngine()