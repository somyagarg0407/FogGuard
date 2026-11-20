"""Device status endpoints (async)."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from datetime import datetime, timezone

from app.database.db import get_db
from app.models.sensor import DeviceStatus
from app.schemas.schemas import DeviceStatusOut
from app.hardware.source import hardware_source
from app.simulation.engine import simulation_engine
from app.core.websocket_manager import manager
from app.core.config import settings

router = APIRouter()


@router.get("/devices/status", summary="Get all device statuses")
async def get_device_statuses(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(DeviceStatus))
    devices = result.scalars().all()

    out = []
    now = datetime.now(timezone.utc)

    for d in devices:
        status = d.connection_status
        last_seen = d.last_seen
        if last_seen and last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)

        # Real-time state overrides
        is_hw_live = hardware_source.is_connected
        is_sim_live = simulation_engine.is_running

        if d.device_name in ("fogguard-esp32", "fogguard-arduino") or d.device_name.startswith("fogguard-sensor-"):
            if is_hw_live:
                status = "CONNECTED"
                last_seen = hardware_source.last_received
            elif is_sim_live:
                status = "SIMULATED"
                last_seen = now
            else:
                status = "DISCONNECTED" if last_seen else "UNKNOWN"

        out.append({
            "id": d.id,
            "device_name": d.device_name,
            "device_type": d.device_type,
            "connection_status": status,
            "last_seen": last_seen.isoformat() if last_seen else None,
            "timestamp": d.timestamp.isoformat() if d.timestamp else None,
        })

    return out


@router.get("/devices/system-info", summary="Get system-level info")
async def get_system_info():
    from app.services.write_queue import write_queue
    from app.hardware.serial_bridge import serial_bridge

    is_hw = hardware_source.is_connected or serial_bridge.is_running
    is_sim = simulation_engine.is_running

    if is_hw:
        active_mode = "HARDWARE"
    elif is_sim:
        active_mode = "SIMULATION"
    else:
        active_mode = "IDLE"

    return {
        "mode": active_mode,
        "simulation_running": is_sim,
        "simulation_scenario": simulation_engine.scenario_name,
        "hardware_connected": is_hw,
        "hardware_last_seen": hardware_source.last_received.isoformat() if hardware_source.last_received else None,
        "serial_bridge_active": serial_bridge.is_running,
        "serial_bridge_port": serial_bridge.current_port,
        "websocket_clients": manager.connection_count,
        "write_queue_pending": write_queue.pending,
        "thresholds": {
            "critical_cm": settings.CRITICAL_THRESHOLD_CM,
            "warning_cm": settings.WARNING_THRESHOLD_CM,
            "caution_cm": settings.CAUTION_THRESHOLD_CM,
            "max_range_cm": settings.MAX_RANGE_CM,
        }
    }


@router.get("/devices/serial/ports", summary="List available USB Serial / COM ports")
async def get_serial_ports():
    """List available COM / tty ports on the host machine for direct Arduino USB connection."""
    from app.hardware.serial_bridge import serial_bridge
    return {
        "ports": serial_bridge.list_ports(),
        "active_port": serial_bridge.current_port,
        "running": serial_bridge.is_running,
    }


@router.post("/devices/serial/connect", summary="Connect direct USB Serial bridge to Arduino")
async def connect_serial(port: Optional[str] = None, baudrate: int = 115200):
    """Start reading from an Arduino plugged directly into USB."""
    from app.hardware.serial_bridge import serial_bridge
    try:
        await serial_bridge.start(port=port, baudrate=baudrate)
        return {"status": "connected", "port": serial_bridge.current_port, "baudrate": baudrate}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@router.post("/devices/serial/disconnect", summary="Disconnect USB Serial bridge")
async def disconnect_serial():
    from app.hardware.serial_bridge import serial_bridge
    await serial_bridge.stop()
    return {"status": "disconnected"}
