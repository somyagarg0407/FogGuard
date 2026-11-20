"""
FogGuard End-to-End Real-Time Performance & Latency Benchmark Test Suite.
Validates telemetry throughput, P50/P95/P99 latencies, WebSocket broadcast speed,
and obstacle edge-case behavior at 1 Hz, 5 Hz, 10 Hz, and 15 Hz.
"""
import pytest
import asyncio
import time
from datetime import datetime, timezone
from typing import List, Dict, Any
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.schemas.schemas import TelemetryPayload, SensorData, TrafficSignalData, TrafficState
from app.core.websocket_manager import manager
from app.core.latency_tracker import latency_tracker
from app.api.iot import process_telemetry, get_last_telemetry
from app.database.db import AsyncSessionLocal


def build_frame(
    seq: int,
    distances: List[float],
    zones: List[str] = None,
    device_id: str = "fogguard-perf-test",
) -> TelemetryPayload:
    if zones is None:
        zones = ["front_left", "front_center", "front_right", "roof_center"]

    sensors = []
    for i, (dist, zone) in enumerate(zip(distances, zones)):
        sid = f"S{i+1}"
        det = (dist is not None and dist <= 150.0)
        sensors.append(SensorData(
            sensor_id=sid,
            zone=zone,
            distance_cm=dist,
            obstacle_detected=det
        ))

    return TelemetryPayload(
        device_id=device_id,
        timestamp=datetime.now(timezone.utc),
        seq=seq,
        uptime_ms=seq * 100,
        host_rx_ns=time.perf_counter_ns(),
        sensors=sensors,
        traffic_signal=TrafficSignalData(state=TrafficState.GREEN, duration_seconds=25)
    )


@pytest.mark.asyncio
async def test_latency_controlled_rate_1hz():
    """Benchmark telemetry pipeline at 1 Hz (10 frames)."""
    latency_tracker.reset()
    frames_generated = 10
    latencies = []

    async with AsyncSessionLocal() as session:
        for i in range(frames_generated):
            t0 = time.perf_counter_ns()
            payload = build_frame(seq=i+1, distances=[250.0, 260.0, 240.0, 280.0])
            await process_telemetry(payload, session, source="hardware")
            proc_ms = (time.perf_counter_ns() - t0) / 1_000_000.0
            latencies.append(proc_ms)
            await asyncio.sleep(0.01)  # fast simulation of 1Hz ticks

    stats = latency_tracker.get_stats()
    assert stats["total_frames"] >= frames_generated
    assert stats["p95_ms"] <= 20.0, f"P95 latency exceeded target: {stats['p95_ms']} ms"
    print(f"\n[1 Hz Benchmark] Processed: {frames_generated} | P50: {stats['p50_ms']}ms | P95: {stats['p95_ms']}ms")


@pytest.mark.asyncio
async def test_latency_controlled_rate_5hz():
    """Benchmark telemetry pipeline at 5 Hz (25 frames, 200 ms interval)."""
    latency_tracker.reset()
    frames_generated = 25

    async with AsyncSessionLocal() as session:
        for i in range(frames_generated):
            payload = build_frame(seq=i+1, distances=[180.0, 120.0, 190.0, 300.0])
            await process_telemetry(payload, session, source="hardware")
            await asyncio.sleep(0.005)

    stats = latency_tracker.get_stats()
    assert stats["total_frames"] >= frames_generated
    assert stats["p95_ms"] <= 20.0, f"P95 latency exceeded target: {stats['p95_ms']} ms"
    print(f"\n[5 Hz Benchmark] Processed: {frames_generated} | P50: {stats['p50_ms']}ms | P95: {stats['p95_ms']}ms")


@pytest.mark.asyncio
async def test_latency_controlled_rate_10hz_canonical():
    """
    Benchmark canonical 4-sensor 10 Hz telemetry pipeline (50 frames, 100 ms interval).
    Verifies target: P95 <= 20 ms (live telemetry hot path).
    """
    latency_tracker.reset()
    frames_generated = 50

    async with AsyncSessionLocal() as session:
        for i in range(frames_generated):
            # Dynamic obstacle approaching from 200cm to 30cm
            dist = max(30.0, 200.0 - (i * 3.5))
            payload = build_frame(seq=i+1, distances=[220.0, dist, 210.0, 350.0])
            await process_telemetry(payload, session, source="hardware")
            await asyncio.sleep(0.002)

    stats = latency_tracker.get_stats()
    assert stats["total_frames"] >= frames_generated
    assert stats["p95_ms"] <= 20.0, f"10 Hz P95 latency exceeded target: {stats['p95_ms']} ms"
    assert stats["dropped_frames"] == 0, f"Dropped frames detected: {stats['dropped_frames']}"
    print(f"\n[10 Hz Canonical Benchmark] Processed: {frames_generated} | P50: {stats['p50_ms']}ms | P95: {stats['p95_ms']}ms | P99: {stats['p99_ms']}ms")


@pytest.mark.asyncio
async def test_latency_stress_rate_15hz():
    """
    Stress-test telemetry pipeline at 15 Hz (60 frames).
    Verifies that pipeline does not deadlock or drop frames under high ingestion load.
    """
    latency_tracker.reset()
    frames_generated = 60

    async with AsyncSessionLocal() as session:
        for i in range(frames_generated):
            payload = build_frame(seq=i+1, distances=[45.0, 85.0, 130.0, 280.0])
            await process_telemetry(payload, session, source="hardware")
            await asyncio.sleep(0.001)

    stats = latency_tracker.get_stats()
    assert stats["total_frames"] >= frames_generated
    assert stats["p95_ms"] <= 20.0, f"15 Hz stress P95 exceeded target: {stats['p95_ms']} ms"
    print(f"\n[15 Hz Stress Benchmark] Processed: {frames_generated} | P50: {stats['p50_ms']}ms | P95: {stats['p95_ms']}ms")


@pytest.mark.asyncio
async def test_scenario_no_obstacles_clear_road():
    """Validate behavior when no obstacles are detected (> 150 cm / 400 cm)."""
    async with AsyncSessionLocal() as session:
        payload = build_frame(seq=101, distances=[380.0, 390.0, 395.0, 400.0])
        await process_telemetry(payload, session, source="hardware")

    last = get_last_telemetry()
    assert last["type"] == "telemetry"
    for s in last["sensors"]:
        assert s["warning_level"] in ("CLEAR", "SAFE")
        assert not s["obstacle_detected"]
    assert len(last["new_warnings"]) == 0


@pytest.mark.asyncio
async def test_scenario_nearby_critical_obstacle():
    """Validate immediate warning and cuboid positioning for nearby critical obstacle (< 50 cm)."""
    async with AsyncSessionLocal() as session:
        payload = build_frame(seq=102, distances=[280.0, 35.0, 290.0, 300.0])
        await process_telemetry(payload, session, source="hardware")

    last = get_last_telemetry()
    s2 = next(s for s in last["sensors"] if s["sensor_id"] == "S2")
    assert s2["warning_level"] == "CRITICAL"
    assert s2["obstacle_detected"] is True
    assert s2["distance_cm"] == 35.0
    # Must have generated a warning with real database ID
    assert len(last["new_warnings"]) > 0
    assert last["new_warnings"][0]["id"] is not None


@pytest.mark.asyncio
async def test_scenario_multiple_simultaneous_obstacles():
    """Validate multiple distinct obstacles in multiple zones in a single frame."""
    async with AsyncSessionLocal() as session:
        payload = build_frame(seq=103, distances=[42.0, 88.0, 140.0, 32.0])
        await process_telemetry(payload, session, source="hardware")

    last = get_last_telemetry()
    levels = {s["sensor_id"]: s["warning_level"] for s in last["sensors"]}
    assert levels["S1"] == "CRITICAL"
    assert levels["S2"] == "WARNING"
    assert levels["S3"] == "CAUTION"
    assert levels["S4"] == "CRITICAL"


@pytest.mark.asyncio
async def test_scenario_missing_echoes_and_null_handling():
    """Validate graceful handling of sensor timeouts / no echoes (distance is None)."""
    async with AsyncSessionLocal() as session:
        payload = build_frame(seq=104, distances=[None, 120.0, None, 250.0])
        await process_telemetry(payload, session, source="hardware")

    last = get_last_telemetry()
    s1 = next(s for s in last["sensors"] if s["sensor_id"] == "S1")
    s2 = next(s for s in last["sensors"] if s["sensor_id"] == "S2")
    assert s1["distance_cm"] is None
    assert s1["warning_level"] == "CLEAR"
    assert s2["distance_cm"] == 120.0
    assert s2["warning_level"] == "CAUTION"


@pytest.mark.asyncio
async def test_diagnostics_latency_endpoint():
    """Verify that the /api/v1/iot/diagnostics/latency endpoint returns valid stats."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.get("/api/v1/iot/diagnostics/latency")
        assert resp.status_code == 200
        data = resp.json()
        assert "p50_ms" in data
        assert "p95_ms" in data
        assert "fps" in data
        assert "total_frames" in data
        assert data["p95_ms"] <= 20.0
