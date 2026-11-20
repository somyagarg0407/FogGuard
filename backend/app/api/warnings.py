"""Warning events REST API endpoints (async)."""
from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, update
from typing import Optional, List
from datetime import datetime

from app.database.db import get_db
from app.models.sensor import WarningEvent
from app.schemas.schemas import WarningEventOut, AcknowledgeWarning

router = APIRouter()


@router.get("/warnings", response_model=List[WarningEventOut], summary="Get warning events")
async def get_warnings(
    sensor_id: Optional[str] = None,
    zone: Optional[str] = None,
    warning_level: Optional[str] = None,
    acknowledged: Optional[bool] = None,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
    limit: int = Query(100, le=1000),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(WarningEvent).order_by(desc(WarningEvent.timestamp))
    if sensor_id:
        stmt = stmt.where(WarningEvent.sensor_id == sensor_id)
    if zone:
        stmt = stmt.where(WarningEvent.zone == zone)
    if warning_level:
        stmt = stmt.where(WarningEvent.warning_level == warning_level.upper())
    if acknowledged is not None:
        stmt = stmt.where(WarningEvent.acknowledged == acknowledged)
    if start_time:
        stmt = stmt.where(WarningEvent.timestamp >= start_time)
    if end_time:
        stmt = stmt.where(WarningEvent.timestamp <= end_time)
    stmt = stmt.offset(offset).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.post("/warnings/acknowledge", summary="Acknowledge a warning")
async def acknowledge_warning(body: AcknowledgeWarning, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(WarningEvent).where(WarningEvent.id == body.warning_id)
    )
    warning = result.scalar_one_or_none()
    if not warning:
        raise HTTPException(404, "Warning not found")
    warning.acknowledged = True
    await db.commit()
    return {"status": "acknowledged", "id": body.warning_id}


@router.post("/warnings/acknowledge-all", summary="Acknowledge all warnings")
async def acknowledge_all_warnings(db: AsyncSession = Depends(get_db)):
    await db.execute(
        update(WarningEvent)
        .where(WarningEvent.acknowledged == False)
        .values(acknowledged=True)
    )
    await db.commit()
    return {"status": "all_acknowledged"}
