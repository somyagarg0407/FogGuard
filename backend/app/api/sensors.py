"""Sensor data REST API endpoints (async)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, func
from typing import Optional, List
from datetime import datetime

from app.database.db import get_db
from app.models.sensor import SensorReading, ObstacleEvent
from app.schemas.schemas import SensorReadingOut, ObstacleEventOut
from app.api.iot import get_last_telemetry

router = APIRouter()


@router.get("/sensors/latest", summary="Get latest sensor readings")
async def get_latest_sensors():
    """Returns the most recently broadcast sensor data."""
    latest = get_last_telemetry()
    if not latest:
        return {"sensors": [], "timestamp": None, "source": "none"}
    return latest


@router.get("/sensors/history", response_model=List[SensorReadingOut], summary="Get sensor reading history")
async def get_sensor_history(
    sensor_id: Optional[str] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(SensorReading).order_by(desc(SensorReading.timestamp))
    if sensor_id:
        stmt = stmt.where(SensorReading.sensor_id == sensor_id)
    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/obstacles", response_model=List[ObstacleEventOut], summary="Get obstacle events")
async def get_obstacles(
    sensor_id: Optional[str] = None,
    zone: Optional[str] = None,
    severity: Optional[str] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(ObstacleEvent).order_by(desc(ObstacleEvent.timestamp))
    if sensor_id:
        stmt = stmt.where(ObstacleEvent.sensor_id == sensor_id)
    if zone:
        stmt = stmt.where(ObstacleEvent.zone == zone)
    if severity:
        stmt = stmt.where(ObstacleEvent.severity == severity.upper())
    if start_time:
        stmt = stmt.where(ObstacleEvent.timestamp >= start_time)
    if end_time:
        stmt = stmt.where(ObstacleEvent.timestamp <= end_time)
    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/obstacles/count", summary="Count obstacle events")
async def count_obstacles(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(func.count(ObstacleEvent.id)))
    return {"count": result.scalar_one()}
