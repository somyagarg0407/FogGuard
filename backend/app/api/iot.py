"""IoT Telemetry endpoint — receives data from ESP32, direct USB serial, or simulation.
Optimized for ultra-low latency, sub-millisecond broadcast, zero disk wait on hot path,
and high-resolution latency instrumentation.
"""
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timezone
import copy
import time
import logging

from app.database.db import get_db, AsyncSessionLocal
from app.schemas.schemas import TelemetryPayload, SimulationControl
from app.services import data_service
from app.services.data_service import precompute_classifications
from app.services.warning_engine import warning_engine
from app.services.write_queue import write_queue
from app.simulation.engine import simulation_engine, SCENARIOS
from app.hardware.source import hardware_source
from app.core.websocket_manager import manager
from app.core.config import settings
from app.core.latency_tracker import latency_tracker

logger = logging.getLogger(__name__)
router = APIRouter()

# Shared mutable state for last telemetry
_last_telemetry: dict = {}
_backend_seq: int = 0


def get_last_telemetry() -> dict:
    """Safe accessor for the most recently broadcast telemetry packet."""
    global _last_telemetry
    return copy.deepcopy(_last_telemetry) if _last_telemetry else {}


async def process_telemetry(
    payload: TelemetryPayload, db: AsyncSession, source: str = "hardware"
):
    """
    Live telemetry processing pipeline (Ultra-Low-Latency):
    1. Precompute distance classifications once per sensor.
    2. Evaluate obstacle warning conditions once per sensor.
    3. Flush WarningEvents to SQLite to allocate genuine database IDs without blocking fsync.
    4. Immediate WebSocket broadcast (sub-millisecond, before any disk commit).
    5. Asynchronously persist warnings and enqueue telemetry to background write queue.
    """
    global _last_telemetry, _backend_seq

    t_proc_start = time.perf_counter_ns()

    if payload.seq is not None:
        seq_num = payload.seq
    else:
        _backend_seq += 1
        seq_num = _backend_seq

    now = payload.timestamp or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    # 1. Precompute classifications once
    levels = precompute_classifications(payload)

    # 2. Build sensor list for broadcast
    sensor_list = []
    for s, (level, _zone) in zip(payload.sensors, levels):
        sensor_list.append({
            "sensor_id": s.sensor_id,
            "zone": s.zone,
            "distance_cm": s.distance_cm,
            "obstacle_detected": s.obstacle_detected,
            "warning_level": level,
        })

    # 3. Warning evaluation — exactly once per reading
    thresholds = {
        "critical_cm": settings.CRITICAL_THRESHOLD_CM,
        "warning_cm": settings.WARNING_THRESHOLD_CM,
        "caution_cm": settings.CAUTION_THRESHOLD_CM,
        "max_range_cm": settings.MAX_RANGE_CM,
    }
    raw_warnings = []
    for s in payload.sensors:
        w = warning_engine.process_sensor(
            s.sensor_id, s.zone, s.distance_cm,
            thresholds=thresholds, now=now,
        )
        if w:
            raw_warnings.append(w)

    # Allocate primary keys for new warnings in SQLite memory (flush without fsync)
    persisted_warnings = []
    if raw_warnings:
        persisted_warnings = await data_service.save_warning_events(db, raw_warnings)
        await db.flush()

    warnings_out = [
        {
            "id": w.id,
            "sensor_id": w.sensor_id,
            "zone": w.zone,
            "distance_cm": w.distance_cm,
            "warning_level": w.warning_level,
            "warning_message": w.warning_message,
            "acknowledged": w.acknowledged,
            "timestamp": w.timestamp.isoformat() if hasattr(w.timestamp, "isoformat") else str(w.timestamp),
        }
        for w in persisted_warnings
    ]

    traffic_out = None
    if payload.traffic_signal:
        traffic_out = {
            "state": payload.traffic_signal.state.value,
            "duration_seconds": payload.traffic_signal.duration_seconds,
        }

    is_sim = (source == "simulation")
    t_proc_end = time.perf_counter_ns()
    backend_proc_ms = (t_proc_end - t_proc_start) / 1_000_000.0

    # Record latency metrics in rolling tracker
    latency_tracker.record(backend_proc_ms, seq=seq_num)

    broadcast_msg = {
        "type": "telemetry",
        "source": source,
        "timestamp": now.isoformat(),
        "sensors": sensor_list,
        "traffic_signal": traffic_out,
        "new_warnings": warnings_out,
        "simulation_mode": is_sim,
        "perf": {
            "seq": seq_num,
            "uptime_ms": payload.uptime_ms,
            "backend_proc_ms": round(backend_proc_ms, 3),
            "host_tx_ms": round(time.time() * 1000, 2),
        },
    }

    _last_telemetry = broadcast_msg

    # 4. Immediate concurrent WebSocket broadcast (sub-millisecond)
    await manager.broadcast(broadcast_msg)

    # 5. Post-broadcast database persistence
    if raw_warnings:
        await db.commit()

    if write_queue.is_running:
        write_queue.enqueue({"payload": payload, "levels": levels})
    else:
        # Fallback inline persistence
        await data_service.save_sensor_readings(db, payload, levels)
        await data_service.save_traffic_event(db, payload)
        await data_service.update_device_status(db, payload.device_id)
        await db.commit()


@router.post("/iot/telemetry", summary="Receive telemetry from ESP32 or hardware")
async def receive_telemetry(
    payload: TelemetryPayload,
    db: AsyncSession = Depends(get_db),
):
    """
    Main endpoint for receiving sensor telemetry from physical hardware (ESP32 / Wi-Fi).
    """
    hardware_source.receive(payload)

    # If simulation was running, stop it so physical hardware takes over exclusively
    if simulation_engine.is_running:
        await simulation_engine.stop()
        logger.info("Paused simulation engine: live hardware telemetry received on /iot/telemetry")

    await process_telemetry(payload, db, source="hardware")
    return {"status": "ok", "processed_sensors": len(payload.sensors)}


@router.post("/iot/traffic_signal", summary="Receive independent traffic signal state from ESP32")
async def receive_traffic_signal(
    payload: dict,
    db: AsyncSession = Depends(get_db),
):
    """
    Receives autonomous traffic signal state emitted by the standalone ESP32 smart traffic light.
    Broadcasts real-time light status (RED/GREEN/YELLOW) and countdown to windshield HUD / dashboard.
    """
    global _last_telemetry

    raw_state = str(payload.get("state") or payload.get("traffic") or "RED").upper()
    dur = payload.get("remaining_seconds") or payload.get("duration_seconds") or payload.get("dur") or 5

    traffic_data = {
        "state": raw_state,
        "duration_seconds": dur,
    }

    # If simulation was running, stop it so physical hardware takes over exclusively
    if simulation_engine.is_running:
        await simulation_engine.stop()
        logger.info("Paused simulation engine: physical ESP32 traffic signal active")

    sensors = _last_telemetry.get("sensors", [])
    now = datetime.now(timezone.utc)

    broadcast_msg = {
        "type": "telemetry",
        "source": "hardware",
        "timestamp": now.isoformat(),
        "sensors": sensors,
        "traffic_signal": traffic_data,
        "new_warnings": [],
        "simulation_mode": False,
        "perf": {
            "seq": _last_telemetry.get("perf", {}).get("seq", 0),
            "uptime_ms": 0,
            "backend_proc_ms": 0.1,
            "host_tx_ms": round(time.time() * 1000, 2),
        },
    }

    _last_telemetry = broadcast_msg
    await manager.broadcast(broadcast_msg)
    return {"status": "ok", "traffic_signal": traffic_data}


@router.get("/iot/diagnostics/latency", summary="Get real-time latency and throughput diagnostics")
async def get_latency_diagnostics():
    """Returns high-resolution P50, P95, P99 latency percentiles, telemetry FPS, and drop metrics."""
    return latency_tracker.get_stats()


@router.post("/simulation/control", summary="Control simulation mode")
async def control_simulation(
    control: SimulationControl,
    db: AsyncSession = Depends(get_db),
):
    """Start, stop, or reset the built-in simulation engine."""
    action = control.action.lower()

    if action == "start":
        scenario = control.scenario or "normal"
        if scenario not in SCENARIOS:
            raise HTTPException(400, f"Unknown scenario. Valid: {list(SCENARIOS.keys())}")
        speed = control.speed_multiplier or 1.0

        async def sim_callback(payload: TelemetryPayload):
            async with AsyncSessionLocal() as session:
                await process_telemetry(payload, session, source="simulation")

        simulation_engine.set_data_callback(sim_callback)
        await simulation_engine.start(scenario=scenario, speed=speed)
        return {"status": "simulation_started", "scenario": scenario, "speed": speed}

    elif action == "stop":
        await simulation_engine.stop()
        return {"status": "simulation_stopped"}

    elif action == "reset":
        simulation_engine.reset()
        return {"status": "simulation_reset"}

    else:
        raise HTTPException(400, f"Unknown action '{action}'. Use: start, stop, reset")


@router.get("/simulation/status", summary="Get simulation status")
async def simulation_status():
    return {
        "running": simulation_engine.is_running,
        "scenario": simulation_engine.scenario_name,
        "scenarios": list(SCENARIOS.keys()),
    }


@router.get("/simulation/scenarios", summary="List available scenarios")
async def list_scenarios():
    return {
        "scenarios": [
            {"id": "normal", "name": "Normal / Clear Road"},
            {"id": "single_obstacle", "name": "Single Obstacle Ahead"},
            {"id": "multiple_obstacles", "name": "Multiple Obstacles"},
            {"id": "critical_front", "name": "Critical Front Obstacle"},
            {"id": "side_obstacle", "name": "Side Obstacle"},
            {"id": "dynamic_approaching", "name": "Dynamic Approaching Obstacle"},
            {"id": "dense_fog", "name": "Dense Fog Demonstration"},
        ]
    }
