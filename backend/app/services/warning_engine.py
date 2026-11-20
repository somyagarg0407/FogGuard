"""Warning engine — generates deduplicated, event-based warnings from sensor data.
"""
from typing import Dict, Optional, Tuple
from datetime import datetime, timezone
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

logger = logging.getLogger(__name__)

ZONE_DISPLAY = {
    "front_left": "Front Left",
    "front_center": "Front Center",
    "front_center_left": "Front Center Left",
    "front_center_right": "Front Center Right",
    "front_right": "Front Right",
    "left_side": "Left Side",
    "right_side": "Right Side",
    "roof_center": "Roof Center",
}


class WarningEngine:
    """
    Generates warnings based on sensor readings.
    Deduplicates: a new warning for the same sensor is only generated
    if the warning level changes or enough time has passed (cooldown).
    """

    COOLDOWN_SECONDS = 10  # min seconds between same-sensor same-level warnings

    def __init__(self):
        # sensor_id -> (level, timestamp)
        self._last_warnings: Dict[str, Tuple[str, datetime]] = {}

    def classify_distance(
        self,
        distance_cm: Optional[float],
        critical: float = 50.0,
        warning: float = 100.0,
        caution: float = 150.0,
        max_range: float = 400.0,
    ) -> str:
        if distance_cm is None or distance_cm <= 0 or distance_cm > max_range:
            return "CLEAR"
        if distance_cm <= critical:
            return "CRITICAL"
        if distance_cm <= warning:
            return "WARNING"
        if distance_cm <= caution:
            return "CAUTION"
        return "SAFE"

    def should_generate_warning(
        self, sensor_id: str, level: str, now: datetime
    ) -> bool:
        if level in ("SAFE", "CLEAR"):
            # Update sensor tracking to SAFE/CLEAR so a future approach triggers immediately
            self._last_warnings[sensor_id] = (level, now)
            return False

        last = self._last_warnings.get(sensor_id)
        if last is None:
            return True

        last_level, last_time = last
        if last_level != level:
            return True

        # Ensure last_time is timezone aware for comparison
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        if (now - last_time).total_seconds() >= self.COOLDOWN_SECONDS:
            return True

        return False

    def build_warning_message(
        self,
        sensor_id: str,
        zone: str,
        distance_cm: Optional[float],
        level: str,
    ) -> str:
        zone_name = ZONE_DISPLAY.get(zone, zone.replace("_", " ").title())
        dist_str = f"{distance_cm:.0f}" if distance_cm is not None else "?"
        if level == "CRITICAL":
            return f"CRITICAL: Obstacle detected {dist_str} cm in {zone_name} zone [{sensor_id}]"
        if level == "WARNING":
            return f"WARNING: Obstacle detected {dist_str} cm in {zone_name} zone [{sensor_id}]"
        if level == "CAUTION":
            return f"CAUTION: Object approaching {zone_name} zone [{sensor_id}] at {dist_str} cm"
        return f"ALERT: Sensor {sensor_id} - {zone_name}"

    def process_sensor(
        self,
        sensor_id: str,
        zone: str,
        distance_cm: Optional[float],
        thresholds: Optional[dict] = None,
        now: Optional[datetime] = None,
    ) -> Optional[dict]:
        """
        Process a sensor reading and return a warning dict if one should be generated,
        or None if no warning is needed.
        """
        if now is None:
            now = datetime.now(timezone.utc)
        elif now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)

        th = thresholds or {}
        level = self.classify_distance(
            distance_cm,
            critical=th.get("critical_cm", 50.0),
            warning=th.get("warning_cm", 100.0),
            caution=th.get("caution_cm", 150.0),
            max_range=th.get("max_range_cm", 400.0),
        )

        if not self.should_generate_warning(sensor_id, level, now):
            return None

        self._last_warnings[sensor_id] = (level, now)
        message = self.build_warning_message(sensor_id, zone, distance_cm, level)
        return {
            "sensor_id": sensor_id,
            "zone": zone,
            "distance_cm": distance_cm,
            "warning_level": level,
            "warning_message": message,
            "acknowledged": False,
            "timestamp": now,
        }

    async def init_from_db(self, db: AsyncSession):
        """Restore last warning state per sensor from the database on startup."""
        try:
            from app.models.sensor import WarningEvent
            result = await db.execute(
                select(WarningEvent).order_by(desc(WarningEvent.timestamp)).limit(50)
            )
            events = result.scalars().all()
            for ev in reversed(events):
                ts = ev.timestamp
                if ts and ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                self._last_warnings[ev.sensor_id] = (ev.warning_level, ts)
            logger.info(f"WarningEngine restored state for {len(self._last_warnings)} sensors from DB")
        except Exception as e:
            logger.warning(f"Could not restore warning state from DB: {e}")

    def reset(self):
        self._last_warnings.clear()


warning_engine = WarningEngine()
