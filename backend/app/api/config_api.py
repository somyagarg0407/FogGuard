"""Settings/configuration API with persistent storage and data retention (async)."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.database.db import get_db
from app.schemas.schemas import ThresholdConfig, DataCleanupResponse
from app.core.config import settings
from app.services import data_service

router = APIRouter()


@router.get("/settings/thresholds", summary="Get current thresholds")
async def get_thresholds():
    return {
        "critical_cm": settings.CRITICAL_THRESHOLD_CM,
        "warning_cm": settings.WARNING_THRESHOLD_CM,
        "caution_cm": settings.CAUTION_THRESHOLD_CM,
        "max_range_cm": settings.MAX_RANGE_CM,
    }


@router.post("/settings/thresholds", summary="Update and persist detection thresholds")
async def update_thresholds(config: ThresholdConfig, db: AsyncSession = Depends(get_db)):
    """
    Update thresholds for the system.
    Persisted to SQLite database so settings survive server restarts.
    """
    settings.CRITICAL_THRESHOLD_CM = config.critical_cm
    settings.WARNING_THRESHOLD_CM = config.warning_cm
    settings.CAUTION_THRESHOLD_CM = config.caution_cm
    settings.MAX_RANGE_CM = config.max_range_cm

    # Persist in DB
    await data_service.persist_thresholds(db, config)

    return {
        "status": "updated_and_persisted",
        "thresholds": {
            "critical_cm": settings.CRITICAL_THRESHOLD_CM,
            "warning_cm": settings.WARNING_THRESHOLD_CM,
            "caution_cm": settings.CAUTION_THRESHOLD_CM,
            "max_range_cm": settings.MAX_RANGE_CM,
        }
    }


@router.post("/settings/cleanup", response_model=DataCleanupResponse, summary="Purge old raw sensor readings")
async def cleanup_data(
    retention_days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    """
    Clean up raw sensor readings older than the specified retention window (default 30 days).
    Obstacle, Warning, and Traffic events are retained for auditing.
    """
    deleted = await data_service.cleanup_old_readings(db, retention_days)
    return DataCleanupResponse(
        deleted_readings=deleted,
        retention_days=retention_days,
        status="cleanup_completed",
    )
