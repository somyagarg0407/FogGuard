import math
from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional
from datetime import datetime, timezone
from enum import Enum


class WarningLevel(str, Enum):
    SAFE = "SAFE"
    CAUTION = "CAUTION"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"
    CLEAR = "CLEAR"


class TrafficState(str, Enum):
    RED = "RED"
    YELLOW = "YELLOW"
    GREEN = "GREEN"


class SensorData(BaseModel):
    sensor_id: str = Field(..., pattern=r"^S[1-6]$")
    zone: str
    distance_cm: Optional[float] = None
    obstacle_detected: bool = False

    @field_validator("distance_cm")
    @classmethod
    def validate_distance(cls, v):
        if v is not None:
            if math.isnan(v) or math.isinf(v):
                raise ValueError("distance_cm must be a finite number")
            if v < 0:
                raise ValueError("distance_cm cannot be negative")
        return v


class TrafficSignalData(BaseModel):
    state: TrafficState
    duration_seconds: Optional[int] = None


class TelemetryPayload(BaseModel):
    device_id: str
    timestamp: Optional[datetime] = None
    seq: Optional[int] = None
    uptime_ms: Optional[int] = None
    host_rx_ns: Optional[int] = None
    sensors: List[SensorData]
    traffic_signal: Optional[TrafficSignalData] = None

    @field_validator("timestamp")
    @classmethod
    def validate_timestamp(cls, v):
        if v is not None:
            if v.tzinfo is None:
                return v.replace(tzinfo=timezone.utc)
            return v.astimezone(timezone.utc)
        return datetime.now(timezone.utc)

    @field_validator("sensors")
    @classmethod
    def validate_sensors(cls, v):
        if len(v) > 6:
            raise ValueError("Maximum 6 sensors allowed")
        if len(v) == 0:
            raise ValueError("Sensors list cannot be empty")
        sensor_ids = [s.sensor_id for s in v]
        if len(sensor_ids) != len(set(sensor_ids)):
            raise ValueError("Duplicate sensor IDs in telemetry packet")
        return v


class SensorReadingOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sensor_id: str
    zone: str
    distance_cm: Optional[float]
    obstacle_detected: bool
    warning_level: Optional[str]
    timestamp: datetime


class ObstacleEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sensor_id: str
    zone: str
    distance_cm: float
    severity: str
    event_type: str
    timestamp: datetime


class WarningEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    sensor_id: str
    zone: str
    distance_cm: Optional[float]
    warning_level: str
    warning_message: str
    acknowledged: bool
    timestamp: datetime


class TrafficSignalEventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    signal_state: str
    duration_seconds: Optional[int]
    timestamp: datetime


class DeviceStatusOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    device_name: str
    device_type: str
    connection_status: str
    last_seen: Optional[datetime]
    timestamp: Optional[datetime] = None


class AnalyticsSummary(BaseModel):
    total_obstacle_detections: int
    total_warning_events: int
    critical_warnings: int
    most_frequent_zone: Optional[str]
    min_obstacle_distance_cm: Optional[float]
    sensor_distribution: dict
    total_traffic_signal_events: int


class SimulationControl(BaseModel):
    action: str  # start, stop, reset
    scenario: Optional[str] = "normal"
    speed_multiplier: Optional[float] = 1.0


class AcknowledgeWarning(BaseModel):
    warning_id: int


class ThresholdConfig(BaseModel):
    critical_cm: float = 50.0
    warning_cm: float = 100.0
    caution_cm: float = 150.0
    max_range_cm: float = 400.0

    @field_validator("critical_cm")
    @classmethod
    def validate_critical(cls, v):
        if v <= 0:
            raise ValueError("critical_cm must be positive")
        return v

    @field_validator("warning_cm")
    @classmethod
    def validate_warning(cls, v, info):
        critical = info.data.get("critical_cm", 50.0)
        if v <= critical:
            raise ValueError("warning_cm must be greater than critical_cm")
        return v

    @field_validator("caution_cm")
    @classmethod
    def validate_caution(cls, v, info):
        warning = info.data.get("warning_cm", 100.0)
        if v <= warning:
            raise ValueError("caution_cm must be greater than warning_cm")
        return v

    @field_validator("max_range_cm")
    @classmethod
    def validate_max_range(cls, v, info):
        caution = info.data.get("caution_cm", 150.0)
        if v <= caution:
            raise ValueError("max_range_cm must be greater than caution_cm")
        return v


class DataCleanupResponse(BaseModel):
    deleted_readings: int
    retention_days: int
    status: str
