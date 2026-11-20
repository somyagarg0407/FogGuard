"""
FogGuard Comprehensive Backend Test Suite.
Verifies telemetry validation, warning engine, persistence, write queue,
operating mode transitions, WebSocket manager, and direct USB serial bridge.
"""
import pytest
import asyncio
import math
from datetime import datetime, timezone, timedelta
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import select, func

from app.main import app
from app.database.db import Base, get_db
import app.database.db as app_db
from app.models.sensor import (
    SensorReading, ObstacleEvent, WarningEvent,
    TrafficSignalEvent, DeviceStatus, SystemConfig
)
from app.services.warning_engine import WarningEngine, warning_engine
from app.services.write_queue import WriteQueue
from app.services import data_service
from app.simulation.engine import (
    SimulationEngine, simulation_engine, SCENARIOS,
    NormalScenario, CriticalFrontObstacleScenario,
    SingleObstacleAheadScenario, MultipleObstaclesScenario,
    SideObstacleScenario, DynamicApproachingScenario, DenseFogScenario
)
from app.hardware.serial_bridge import SerialHardwareBridge
from app.hardware.source import hardware_source
from app.core.websocket_manager import ConnectionManager


# ─── Isolated Test Database ──────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_fogguard.db"
test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestingSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# Route background tasks and services to the test database
app_db.AsyncSessionLocal = TestingSessionLocal
app_db.engine = test_engine


@pytest.fixture(autouse=True)
async def setup_test_database():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest.fixture()
async def db():
    async with TestingSessionLocal() as session:
        yield session


@pytest.fixture()
async def client(db):
    async def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def reset_singletons():
    warning_engine.reset()
    yield
    warning_engine.reset()


# ─── 1. Telemetry Ingestion & Validation ──────────────────────────────────────
class TestTelemetryValidation:
    @pytest.mark.asyncio
    async def test_valid_six_sensor_telemetry(self, client):
        payload = {
            "device_id": "esp32-gateway-01",
            "sensors": [
                {"sensor_id": "S1", "zone": "front_left", "distance_cm": 45.0, "obstacle_detected": True},
                {"sensor_id": "S2", "zone": "front_center_left", "distance_cm": 120.0, "obstacle_detected": True},
                {"sensor_id": "S3", "zone": "front_center_right", "distance_cm": 200.0, "obstacle_detected": False},
                {"sensor_id": "S4", "zone": "front_right", "distance_cm": 250.0, "obstacle_detected": False},
                {"sensor_id": "S5", "zone": "left_side", "distance_cm": 80.0, "obstacle_detected": True},
                {"sensor_id": "S6", "zone": "right_side", "distance_cm": 180.0, "obstacle_detected": False},
            ],
            "traffic_signal": {"state": "GREEN", "duration_seconds": 30}
        }
        res = await client.post("/api/v1/iot/telemetry", json=payload)
        assert res.status_code == 200
        assert res.json()["processed_sensors"] == 6

    @pytest.mark.asyncio
    async def test_valid_four_sensor_telemetry(self, client):
        payload = {
            "device_id": "arduino-uno-01",
            "sensors": [
                {"sensor_id": "S1", "zone": "front_left", "distance_cm": 60.0, "obstacle_detected": True},
                {"sensor_id": "S2", "zone": "front_center", "distance_cm": 90.0, "obstacle_detected": True},
                {"sensor_id": "S3", "zone": "front_right", "distance_cm": 140.0, "obstacle_detected": True},
                {"sensor_id": "S4", "zone": "roof_center", "distance_cm": 220.0, "obstacle_detected": False},
            ],
        }
        res = await client.post("/api/v1/iot/telemetry", json=payload)
        assert res.status_code == 200
        assert res.json()["processed_sensors"] == 4

    @pytest.mark.asyncio
    async def test_invalid_sensor_id_rejected(self, client):
        payload = {
            "device_id": "test-device",
            "sensors": [
                {"sensor_id": "S7", "zone": "rear", "distance_cm": 50.0, "obstacle_detected": True},
            ],
        }
        res = await client.post("/api/v1/iot/telemetry", json=payload)
        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_duplicate_sensor_ids_rejected(self, client):
        payload = {
            "device_id": "test-device",
            "sensors": [
                {"sensor_id": "S1", "zone": "front_left", "distance_cm": 50.0, "obstacle_detected": True},
                {"sensor_id": "S1", "zone": "front_left", "distance_cm": 60.0, "obstacle_detected": True},
            ],
        }
        res = await client.post("/api/v1/iot/telemetry", json=payload)
        assert res.status_code == 422
        assert "Duplicate sensor IDs" in res.text

    @pytest.mark.asyncio
    async def test_missing_null_distance_reading(self, client):
        payload = {
            "device_id": "test-device",
            "sensors": [
                {"sensor_id": "S1", "zone": "front_left", "distance_cm": None, "obstacle_detected": False},
            ],
        }
        res = await client.post("/api/v1/iot/telemetry", json=payload)
        assert res.status_code == 200

    @pytest.mark.asyncio
    async def test_negative_distance_rejected(self, client):
        payload = {
            "device_id": "test-device",
            "sensors": [
                {"sensor_id": "S1", "zone": "front_left", "distance_cm": -15.0, "obstacle_detected": False},
            ],
        }
        res = await client.post("/api/v1/iot/telemetry", json=payload)
        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_invalid_traffic_state_rejected(self, client):
        payload = {
            "device_id": "test-device",
            "sensors": [{"sensor_id": "S1", "zone": "front_left", "distance_cm": 100.0}],
            "traffic_signal": {"state": "BLUE"}
        }
        res = await client.post("/api/v1/iot/telemetry", json=payload)
        assert res.status_code == 422

    @pytest.mark.asyncio
    async def test_hardware_telemetry_source_flag(self, client):
        payload = {
            "device_id": "esp32-real-hardware",
            "sensors": [{"sensor_id": "S1", "zone": "front_left", "distance_cm": 42.0, "obstacle_detected": True}],
        }
        res = await client.post("/api/v1/iot/telemetry", json=payload)
        assert res.status_code == 200

        # Verify latest telemetry records hardware source, NOT simulation
        res_latest = await client.get("/api/v1/sensors/latest")
        assert res_latest.status_code == 200
        data = res_latest.json()
        assert data["source"] == "hardware"
        assert data["simulation_mode"] is False


# ─── 2. Warning Engine Architecture ──────────────────────────────────────────
class TestWarningEngineArchitecture:
    def test_classifications(self):
        engine = WarningEngine()
        assert engine.classify_distance(20.0) == "CRITICAL"
        assert engine.classify_distance(50.0) == "CRITICAL"
        assert engine.classify_distance(50.1) == "WARNING"
        assert engine.classify_distance(100.0) == "WARNING"
        assert engine.classify_distance(100.1) == "CAUTION"
        assert engine.classify_distance(150.0) == "CAUTION"
        assert engine.classify_distance(150.1) == "SAFE"
        assert engine.classify_distance(300.0) == "SAFE"
        assert engine.classify_distance(450.0) == "CLEAR"
        assert engine.classify_distance(None) == "CLEAR"
        assert engine.classify_distance(0.0) == "CLEAR"
        assert engine.classify_distance(-5.0) == "CLEAR"

    def test_initial_warning_generation(self):
        engine = WarningEngine()
        now = datetime.now(timezone.utc)
        w = engine.process_sensor("S1", "front_left", 35.0, now=now)
        assert w is not None
        assert w["sensor_id"] == "S1"
        assert w["warning_level"] == "CRITICAL"
        assert "CRITICAL" in w["warning_message"]

    def test_repeated_warning_suppression_cooldown(self):
        engine = WarningEngine()
        t0 = datetime(2026, 11, 15, 10, 0, 0, tzinfo=timezone.utc)
        w1 = engine.process_sensor("S1", "front_left", 35.0, now=t0)
        assert w1 is not None

        # 4 seconds later at same level — should be suppressed
        t1 = t0 + timedelta(seconds=4)
        w2 = engine.process_sensor("S1", "front_left", 40.0, now=t1)
        assert w2 is None

        # 12 seconds later (> 10s cooldown) — should generate new warning
        t2 = t0 + timedelta(seconds=12)
        w3 = engine.process_sensor("S1", "front_left", 42.0, now=t2)
        assert w3 is not None
        assert w3["warning_level"] == "CRITICAL"

    def test_severity_change_bypasses_cooldown(self):
        engine = WarningEngine()
        t0 = datetime(2026, 11, 15, 10, 0, 0, tzinfo=timezone.utc)
        w1 = engine.process_sensor("S1", "front_left", 80.0, now=t0)  # WARNING
        assert w1 is not None
        assert w1["warning_level"] == "WARNING"

        # 2 seconds later, obstacle suddenly gets closer (CRITICAL)
        t1 = t0 + timedelta(seconds=2)
        w2 = engine.process_sensor("S1", "front_left", 30.0, now=t1)  # CRITICAL
        assert w2 is not None
        assert w2["warning_level"] == "CRITICAL"

    @pytest.mark.asyncio
    async def test_warning_db_persistence_and_real_id(self, client, db):
        # Ingest telemetry that triggers a warning
        payload = {
            "device_id": "test-device",
            "sensors": [{"sensor_id": "S1", "zone": "front_left", "distance_cm": 25.0, "obstacle_detected": True}]
        }
        res = await client.post("/api/v1/iot/telemetry", json=payload)
        assert res.status_code == 200

        # Verify warning was persisted in SQLite
        res_w = await client.get("/api/v1/warnings?sensor_id=S1")
        assert res_w.status_code == 200
        warnings = res_w.json()
        assert len(warnings) >= 1
        w = warnings[0]
        assert isinstance(w["id"], int)
        assert w["id"] > 0
        assert w["warning_level"] == "CRITICAL"
        assert w["acknowledged"] is False

    @pytest.mark.asyncio
    async def test_single_and_bulk_acknowledgement(self, client, db):
        # Post a critical reading
        payload = {
            "device_id": "test-device",
            "sensors": [{"sensor_id": "S2", "zone": "front_center_left", "distance_cm": 30.0, "obstacle_detected": True}]
        }
        await client.post("/api/v1/iot/telemetry", json=payload)

        # Get the real warning ID
        res = await client.get("/api/v1/warnings?sensor_id=S2")
        warnings = res.json()
        assert len(warnings) > 0
        wid = warnings[0]["id"]

        # Acknowledge single warning
        ack_res = await client.post("/api/v1/warnings/acknowledge", json={"warning_id": wid})
        assert ack_res.status_code == 200
        assert ack_res.json()["status"] == "acknowledged"

        # Verify DB reflects acknowledged=True
        verify_res = await client.get(f"/api/v1/warnings?sensor_id=S2")
        updated_w = [w for w in verify_res.json() if w["id"] == wid][0]
        assert updated_w["acknowledged"] is True

        # Test bulk acknowledge
        bulk_res = await client.post("/api/v1/warnings/acknowledge-all")
        assert bulk_res.status_code == 200
        assert bulk_res.json()["status"] == "all_acknowledged"


# ─── 3. Database Persistence & Integrity ─────────────────────────────────────
class TestDatabaseIntegrity:
    @pytest.mark.asyncio
    async def test_sensor_and_obstacle_events_persistence(self, client, db):
        payload = {
            "device_id": "test-device",
            "sensors": [
                {"sensor_id": "S5", "zone": "left_side", "distance_cm": 40.0, "obstacle_detected": True},
                {"sensor_id": "S6", "zone": "right_side", "distance_cm": 300.0, "obstacle_detected": False},
            ]
        }
        res = await client.post("/api/v1/iot/telemetry", json=payload)
        assert res.status_code == 200

        # Obstacle event check (S5 <= 150 cm should be recorded)
        res_obs = await client.get("/api/v1/obstacles?sensor_id=S5")
        assert res_obs.status_code == 200
        obs = res_obs.json()
        assert len(obs) >= 1
        assert obs[0]["sensor_id"] == "S5"
        assert obs[0]["severity"] == "CRITICAL"

    @pytest.mark.asyncio
    async def test_traffic_signal_event_persistence_on_change(self, client, db):
        # First signal: RED
        p1 = {
            "device_id": "test-device",
            "sensors": [{"sensor_id": "S1", "zone": "front_left", "distance_cm": 200.0}],
            "traffic_signal": {"state": "RED", "duration_seconds": 30}
        }
        await client.post("/api/v1/iot/telemetry", json=p1)

        # Same signal: RED (should NOT duplicate)
        await client.post("/api/v1/iot/telemetry", json=p1)

        # Changed signal: GREEN
        p2 = {
            "device_id": "test-device",
            "sensors": [{"sensor_id": "S1", "zone": "front_left", "distance_cm": 200.0}],
            "traffic_signal": {"state": "GREEN", "duration_seconds": 25}
        }
        await client.post("/api/v1/iot/telemetry", json=p2)

        res_traf = await client.get("/api/v1/traffic/history")
        assert res_traf.status_code == 200
        events = res_traf.json()
        assert len(events) >= 2
        states = [e["signal_state"] for e in events]
        assert "RED" in states and "GREEN" in states

    @pytest.mark.asyncio
    async def test_threshold_persistence_in_db(self, client, db):
        new_th = {
            "critical_cm": 45.0,
            "warning_cm": 95.0,
            "caution_cm": 145.0,
            "max_range_cm": 380.0,
        }
        res = await client.post("/api/v1/settings/thresholds", json=new_th)
        assert res.status_code == 200

        # Query DB directly to verify SystemConfig record
        row = (await db.execute(select(SystemConfig).where(SystemConfig.key == "thresholds"))).scalar_one_or_none()
        assert row is not None
        assert "45.0" in row.value

    @pytest.mark.asyncio
    async def test_data_cleanup_preserves_warnings_and_obstacles(self, client, db):
        # Insert historical sensor reading older than 40 days
        old_time = datetime.now(timezone.utc) - timedelta(days=45)
        old_reading = SensorReading(
            sensor_id="S1", zone="front_left", distance_cm=180.0,
            obstacle_detected=False, warning_level="SAFE", timestamp=old_time
        )
        old_warning = WarningEvent(
            sensor_id="S1", zone="front_left", distance_cm=30.0,
            warning_level="CRITICAL", warning_message="Historical Warning",
            acknowledged=True, timestamp=old_time
        )
        db.add(old_reading)
        db.add(old_warning)
        await db.commit()

        # Run cleanup for retention > 30 days
        cleanup_res = await client.post("/api/v1/settings/cleanup?retention_days=30")
        assert cleanup_res.status_code == 200
        data = cleanup_res.json()
        assert data["deleted_readings"] >= 1

        # Verify old WarningEvent is still preserved
        warn_check = (await db.execute(select(WarningEvent).where(WarningEvent.warning_message == "Historical Warning"))).scalars().all()
        assert len(warn_check) >= 1


# ─── 4. Reliable Write Queue ─────────────────────────────────────────────────
class TestReliableWriteQueue:
    @pytest.mark.asyncio
    async def test_write_queue_flushes_items(self):
        flushed_batches = []

        async def mock_flush(batch):
            flushed_batches.append(list(batch))

        wq = WriteQueue(flush_interval_ms=50, max_batch_size=10, max_queue_size=100)
        wq.set_flush_callback(mock_flush)
        await wq.start()

        for i in range(15):
            wq.enqueue(f"item_{i}")

        await asyncio.sleep(0.15)
        await wq.stop()

        all_flushed = [item for b in flushed_batches for item in b]
        assert len(all_flushed) == 15
        assert wq.pending == 0

    @pytest.mark.asyncio
    async def test_write_queue_retries_on_failure(self):
        attempt_count = 0
        flushed_items = []

        async def fail_once_flush(batch):
            nonlocal attempt_count
            attempt_count += 1
            if attempt_count == 1:
                raise RuntimeError("Simulated DB Lock Error")
            flushed_items.extend(batch)

        wq = WriteQueue(flush_interval_ms=50, max_batch_size=10, max_queue_size=100)
        wq.set_flush_callback(fail_once_flush)

        wq.enqueue("critical_item_1")
        wq.enqueue("critical_item_2")

        # First flush will fail
        await wq._flush_once()
        assert attempt_count == 1
        assert wq.pending == 2  # Items must NOT have been lost!

        # Second flush succeeds
        await wq._flush_once()
        assert attempt_count == 2
        assert len(flushed_items) == 2
        assert wq.pending == 0

    @pytest.mark.asyncio
    async def test_write_queue_bounded_backpressure(self):
        wq = WriteQueue(flush_interval_ms=1000, max_batch_size=10, max_queue_size=5)
        for i in range(10):
            wq.enqueue(f"msg_{i}")

        assert wq.pending == 5
        # The oldest items (0-4) were dropped to protect memory, newest (5-9) kept
        assert list(wq._queue) == [f"msg_{i}" for i in range(5, 10)]

    @pytest.mark.asyncio
    async def test_write_queue_shutdown_drain_all(self):
        drained = []

        async def record_flush(batch):
            drained.extend(batch)

        wq = WriteQueue(flush_interval_ms=1000, max_batch_size=5, max_queue_size=50)
        wq.set_flush_callback(record_flush)
        await wq.start()

        # Enqueue 14 items (almost 3 full batches)
        for i in range(14):
            wq.enqueue(f"data_{i}")

        assert wq.pending == 14
        # Graceful shutdown must drain all 14 items across all batches
        await wq.stop()
        assert wq.pending == 0
        assert len(drained) == 14


# ─── 5. Simulation Scenarios & Operating Mode ────────────────────────────────
class TestSimulationAndOperatingMode:
    def test_all_seven_scenarios_produce_valid_data(self):
        for scenario_name, scenario_cls in SCENARIOS.items():
            scenario = scenario_cls(scenario_name)
            for _ in range(5):
                data = scenario.get_readings()
                assert "distances" in data
                assert "traffic_state" in data
                assert data["traffic_state"] in ("RED", "GREEN", "YELLOW")
                for sid in ("S1", "S2", "S3", "S4", "S5", "S6"):
                    assert sid in data["distances"]

    @pytest.mark.asyncio
    async def test_simulation_start_stop_control(self, client):
        res_start = await client.post("/api/v1/simulation/control", json={"action": "start", "scenario": "critical_front", "speed_multiplier": 2.0})
        assert res_start.status_code == 200
        assert res_start.json()["status"] == "simulation_started"

        res_status = await client.get("/api/v1/simulation/status")
        assert res_status.status_code == 200
        assert res_status.json()["running"] is True
        assert res_status.json()["scenario"] == "critical_front"

        res_stop = await client.post("/api/v1/simulation/control", json={"action": "stop"})
        assert res_stop.status_code == 200
        assert res_stop.json()["status"] == "simulation_stopped"

    @pytest.mark.asyncio
    async def test_hardware_overrides_running_simulation(self, client):
        # 1. Start simulation
        await client.post("/api/v1/simulation/control", json={"action": "start", "scenario": "normal"})
        assert simulation_engine.is_running is True

        # 2. Ingest hardware telemetry
        payload = {
            "device_id": "esp32-real-hardware",
            "sensors": [{"sensor_id": "S1", "zone": "front_left", "distance_cm": 55.0, "obstacle_detected": True}]
        }
        res = await client.post("/api/v1/iot/telemetry", json=payload)
        assert res.status_code == 200

        # Simulation must be automatically stopped so hardware does not fight with simulation
        assert simulation_engine.is_running is False


# ─── 6. WebSocket Manager Concurrency & Safety ───────────────────────────────
class TestWebSocketManager:
    @pytest.mark.asyncio
    async def test_concurrent_broadcast_safety(self):
        mgr = ConnectionManager()

        class MockWS:
            def __init__(self, fail=False):
                self.fail = fail
                self.messages = []

            async def accept(self):
                pass

            async def send_text(self, text):
                if self.fail:
                    raise ConnectionResetError("Client dropped connection")
                self.messages.append(text)

        ws1 = MockWS(fail=False)
        ws2 = MockWS(fail=True)  # Broken client
        ws3 = MockWS(fail=False)

        await mgr.connect(ws1)
        await mgr.connect(ws2)
        await mgr.connect(ws3)
        assert mgr.connection_count == 3

        # Broadcast should deliver to ws1 and ws3, prune ws2, and not crash
        await mgr.broadcast({"type": "test_broadcast", "data": 123})

        assert len(ws1.messages) == 1
        assert len(ws3.messages) == 1
        # Dead client ws2 was pruned
        assert mgr.connection_count == 2
        assert ws2 not in mgr.active_connections

        # Test disconnect all on shutdown
        await mgr.disconnect_all()
        assert mgr.connection_count == 0


# ─── 7. Direct USB Serial Protocol Parsing ───────────────────────────────────
class TestSerialProtocolParsing:
    def test_json_line_parsing(self):
        bridge = SerialHardwareBridge()
        json_line = '{"traffic":"GREEN","dur":25,"sensors":[{"id":"S1","dist":45.2,"det":true},{"id":"S2","dist":120.0,"det":true}]}'
        result = bridge._process_incoming_line(json_line)
        assert result is not None
        assert len(result["sensors"]) == 2
        assert result["sensors"][0]["sensor_id"] == "S1"
        assert result["sensors"][0]["distance_cm"] == 45.2
        assert result["traffic_signal"]["state"] == "GREEN"

    def test_six_sensor_line_by_line_parsing(self):
        bridge = SerialHardwareBridge()
        lines = [
            "Sensor 1: 35.50 cm",
            "Sensor 2: 78.20 cm",
            "Sensor 3: 110.00 cm",
            "Sensor 4: 155.00 cm",
            "Sensor 5: 90.00 cm",
            "Sensor 6: No Echo",
        ]
        results = [bridge._process_incoming_line(line) for line in lines]
        # Lines 1-5 buffer data; line 6 completes the cycle and produces the payload
        assert results[0] is None
        assert results[4] is None
        final_payload = results[5]
        assert final_payload is not None
        assert len(final_payload["sensors"]) == 6
        assert final_payload["sensors"][0]["distance_cm"] == 35.5
        assert final_payload["sensors"][5]["distance_cm"] is None
        assert final_payload["sensors"][5]["obstacle_detected"] is False

    def test_malformed_serial_lines_ignored_safely(self):
        bridge = SerialHardwareBridge()
        assert bridge._process_incoming_line("") is None
        assert bridge._process_incoming_line("Corrupted junk \x00\xff data") is None
        assert bridge._process_incoming_line("Sensor 99: 100 cm") is None


# ─── 8. System, Health, Analytics & Edge Cases ───────────────────────────────
class TestSystemAndAnalyticsEndpoints:
    @pytest.mark.asyncio
    async def test_health_check(self, client):
        res = await client.get("/health")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "healthy"
        assert "websocket_clients" in data
        assert "write_queue_pending" in data

    @pytest.mark.asyncio
    async def test_root(self, client):
        res = await client.get("/")
        assert res.status_code == 200
        assert "websocket" in res.json()

    @pytest.mark.asyncio
    async def test_simulation_scenarios_endpoint(self, client):
        res = await client.get("/api/v1/simulation/scenarios")
        assert res.status_code == 200
        data = res.json()
        assert len(data["scenarios"]) == 7

    @pytest.mark.asyncio
    async def test_obstacles_count_endpoint(self, client):
        res = await client.get("/api/v1/obstacles/count")
        assert res.status_code == 200
        assert "count" in res.json()

    @pytest.mark.asyncio
    async def test_analytics_summary_and_breakdowns(self, client):
        res = await client.get("/api/v1/analytics/summary")
        assert res.status_code == 200
        data = res.json()
        assert "total_obstacle_detections" in data
        assert "total_warning_events" in data

        res_obs = await client.get("/api/v1/analytics/obstacles-over-time")
        assert res_obs.status_code == 200

        res_warn = await client.get("/api/v1/analytics/warnings-over-time")
        assert res_warn.status_code == 200

        res_traf = await client.get("/api/v1/analytics/traffic-distribution")
        assert res_traf.status_code == 200

        res_heat = await client.get("/api/v1/analytics/sensor-heatmap")
        assert res_heat.status_code == 200

    @pytest.mark.asyncio
    async def test_devices_system_info(self, client):
        res = await client.get("/api/v1/devices/system-info")
        assert res.status_code == 200
        data = res.json()
        assert "mode" in data
        assert "thresholds" in data

    @pytest.mark.asyncio
    async def test_acknowledge_nonexistent_warning_returns_404(self, client):
        res = await client.post("/api/v1/warnings/acknowledge", json={"warning_id": 999999})
        assert res.status_code == 404

    @pytest.mark.asyncio
    async def test_threshold_invalid_hierarchy_returns_422(self, client):
        res = await client.post("/api/v1/settings/thresholds", json={
            "critical_cm": 100.0,
            "warning_cm": 50.0,  # warning < critical is invalid
            "caution_cm": 150.0,
            "max_range_cm": 400.0,
        })
        assert res.status_code == 422

