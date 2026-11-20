"""Analytics endpoints — derived from actual DB records (async)."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, desc

from app.database.db import get_db
from app.models.sensor import ObstacleEvent, WarningEvent, TrafficSignalEvent
from app.schemas.schemas import AnalyticsSummary

router = APIRouter()


@router.get("/analytics/summary", response_model=AnalyticsSummary, summary="Analytics summary")
async def get_analytics_summary(db: AsyncSession = Depends(get_db)):
    total_obstacles = (await db.execute(
        select(func.count(ObstacleEvent.id))
    )).scalar_one()

    total_warnings = (await db.execute(
        select(func.count(WarningEvent.id))
    )).scalar_one()

    critical_warnings = (await db.execute(
        select(func.count(WarningEvent.id))
        .where(WarningEvent.warning_level == "CRITICAL")
    )).scalar_one()

    # Most frequent zone
    zone_row = (await db.execute(
        select(ObstacleEvent.zone, func.count(ObstacleEvent.id).label("cnt"))
        .group_by(ObstacleEvent.zone)
        .order_by(desc("cnt"))
        .limit(1)
    )).first()
    most_frequent_zone = zone_row[0] if zone_row else None

    # Min distance
    min_dist_row = (await db.execute(
        select(func.min(ObstacleEvent.distance_cm))
    )).scalar_one()

    # Sensor distribution
    sensor_rows = (await db.execute(
        select(ObstacleEvent.sensor_id, func.count(ObstacleEvent.id).label("cnt"))
        .group_by(ObstacleEvent.sensor_id)
    )).all()
    sensor_dist = {row[0]: row[1] for row in sensor_rows}

    total_traffic = (await db.execute(
        select(func.count(TrafficSignalEvent.id))
    )).scalar_one()

    return AnalyticsSummary(
        total_obstacle_detections=total_obstacles,
        total_warning_events=total_warnings,
        critical_warnings=critical_warnings,
        most_frequent_zone=most_frequent_zone,
        min_obstacle_distance_cm=min_dist_row,
        sensor_distribution=sensor_dist,
        total_traffic_signal_events=total_traffic,
    )


@router.get("/analytics/obstacles-over-time", summary="Obstacle detections over time")
async def obstacles_over_time(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(
            func.strftime("%Y-%m-%d %H:00", ObstacleEvent.timestamp).label("hour"),
            func.count(ObstacleEvent.id).label("count"),
        )
        .group_by("hour")
        .order_by("hour")
        .limit(48)
    )).all()
    return [{"time": r[0], "count": r[1]} for r in rows]


@router.get("/analytics/warnings-over-time", summary="Warning frequency over time")
async def warnings_over_time(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(
            func.strftime("%Y-%m-%d %H:00", WarningEvent.timestamp).label("hour"),
            WarningEvent.warning_level,
            func.count(WarningEvent.id).label("count"),
        )
        .group_by("hour", WarningEvent.warning_level)
        .order_by("hour")
        .limit(96)
    )).all()
    return [{"time": r[0], "level": r[1], "count": r[2]} for r in rows]


@router.get("/analytics/traffic-distribution", summary="Traffic signal state distribution")
async def traffic_distribution(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(
            TrafficSignalEvent.signal_state,
            func.count(TrafficSignalEvent.id).label("count"),
        )
        .group_by(TrafficSignalEvent.signal_state)
    )).all()
    return [{"state": r[0], "count": r[1]} for r in rows]


@router.get("/analytics/sensor-heatmap", summary="Sensor detection heatmap data")
async def sensor_heatmap(db: AsyncSession = Depends(get_db)):
    rows = (await db.execute(
        select(
            ObstacleEvent.sensor_id,
            ObstacleEvent.severity,
            func.count(ObstacleEvent.id).label("count"),
        )
        .group_by(ObstacleEvent.sensor_id, ObstacleEvent.severity)
    )).all()
    return [{"sensor_id": r[0], "severity": r[1], "count": r[2]} for r in rows]
