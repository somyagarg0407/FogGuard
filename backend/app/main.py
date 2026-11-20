"""
FogGuard FastAPI Backend
IoT-based fog-resistant obstacle detection & smart traffic management system.
"""
import logging
import asyncio
from contextlib import asynccontextmanager
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.core.websocket_manager import manager
from app.database.db import init_db, get_db, AsyncSessionLocal, engine
from app.api import iot, sensors, warnings, traffic, analytics, devices, config_api
from app.services.data_service import init_devices, load_persistent_settings, flush_write_batch
from app.services.warning_engine import warning_engine
from app.services.write_queue import write_queue
from app.simulation.engine import simulation_engine
from app.hardware.serial_bridge import serial_bridge
from app.api.iot import get_last_telemetry, process_telemetry

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and graceful shutdown lifecycle."""
    logger.info("FogGuard backend starting up...")

    # 1. Initialize database tables first
    await init_db()
    logger.info("Database initialized")

    # 2. Initialize default device records, persistent thresholds, and warning state
    async with AsyncSessionLocal() as db:
        await init_devices(db)
        await load_persistent_settings(db)
        await warning_engine.init_from_db(db)

    # 3. Start the reliable batch write queue
    write_queue.set_flush_callback(flush_write_batch)
    await write_queue.start()
    logger.info("Batch write queue started")

    # 4. Auto-start simulation if configured
    if settings.SIMULATION_MODE:
        async def sim_callback(payload):
            async with AsyncSessionLocal() as session:
                await process_telemetry(payload, session, source="simulation")

        simulation_engine.set_data_callback(sim_callback)
        await simulation_engine.start(scenario="normal", speed=1.0)
        logger.info("Simulation auto-started in SIMULATION_MODE")

    logger.info("FogGuard backend ready on http://0.0.0.0:8000")
    yield

    # Shutdown sequence
    logger.info("FogGuard backend shutting down...")
    try:
        await simulation_engine.stop()
    except Exception as e:
        logger.error(f"Error stopping simulation: {e}")

    try:
        await serial_bridge.stop()
    except Exception as e:
        logger.error(f"Error stopping serial bridge: {e}")

    try:
        await write_queue.stop()
    except Exception as e:
        logger.error(f"Error stopping write queue: {e}")

    try:
        await manager.disconnect_all()
    except Exception as e:
        logger.error(f"Error closing WebSockets: {e}")

    try:
        await engine.dispose()
    except Exception as e:
        logger.error(f"Error disposing database engine: {e}")

    logger.info("FogGuard backend shutdown complete.")


app = FastAPI(
    title="FogGuard API",
    description="IoT-based fog-resistant obstacle detection and smart traffic management system.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Proper CORS policy with credentials and localhost regex support
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routes
PREFIX = "/api/v1"
app.include_router(iot.router, prefix=PREFIX, tags=["IoT / Simulation"])
app.include_router(sensors.router, prefix=PREFIX, tags=["Sensors"])
app.include_router(warnings.router, prefix=PREFIX, tags=["Warnings"])
app.include_router(traffic.router, prefix=PREFIX, tags=["Traffic"])
app.include_router(analytics.router, prefix=PREFIX, tags=["Analytics"])
app.include_router(devices.router, prefix=PREFIX, tags=["Devices"])
app.include_router(config_api.router, prefix=PREFIX, tags=["Settings"])


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Real-time WebSocket endpoint for dashboard telemetry updates."""
    await manager.connect(websocket)
    try:
        # Send latest state immediately upon connection
        latest = get_last_telemetry()
        if latest:
            await manager.send_personal_message(latest, websocket)

        # Keep connection alive with periodic pings
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
            except asyncio.TimeoutError:
                await websocket.send_text('{"type":"ping"}')
    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.warning(f"WebSocket client error: {e}")
        await manager.disconnect(websocket)


@app.get("/health", tags=["Health"])
async def health_check():
    return {
        "status": "healthy",
        "service": "FogGuard Backend",
        "version": "1.0.0",
        "simulation_running": simulation_engine.is_running,
        "websocket_clients": manager.connection_count,
        "write_queue_pending": write_queue.pending,
    }


@app.get("/", tags=["Health"])
async def root():
    return {
        "message": "FogGuard IoT Backend",
        "docs": "/docs",
        "websocket": "ws://localhost:8000/ws",
    }
