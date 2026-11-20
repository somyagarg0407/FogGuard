"""
Hardware data source abstraction.
When hardware mode is active, real ESP32 data arrives via POST /api/v1/iot/telemetry.
This module tracks the last received hardware payload.
"""
from typing import Optional
from datetime import datetime, timezone
from app.schemas.schemas import TelemetryPayload


class HardwareDataSource:
    def __init__(self):
        self._last_payload: Optional[TelemetryPayload] = None
        self._last_received: Optional[datetime] = None

    def receive(self, payload: TelemetryPayload):
        self._last_payload = payload
        self._last_received = datetime.now(timezone.utc)

    @property
    def last_payload(self) -> Optional[TelemetryPayload]:
        return self._last_payload

    @property
    def last_received(self) -> Optional[datetime]:
        return self._last_received

    @property
    def is_connected(self) -> bool:
        if self._last_received is None:
            return False
        delta = (datetime.now(timezone.utc) - self._last_received).total_seconds()
        return delta < 10.0  # Consider disconnected if no data for 10 seconds


hardware_source = HardwareDataSource()
