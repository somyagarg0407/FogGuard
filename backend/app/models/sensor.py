from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, func
from app.database.db import Base


class SensorReading(Base):
    __tablename__ = "sensor_readings"

    id = Column(Integer, primary_key=True, index=True)
    sensor_id = Column(String(10), nullable=False, index=True)
    zone = Column(String(50), nullable=False, index=True)
    distance_cm = Column(Float, nullable=True)
    obstacle_detected = Column(Boolean, default=False)
    warning_level = Column(String(20), nullable=True, index=True)  # SAFE, CAUTION, WARNING, CRITICAL
    timestamp = Column(DateTime, default=func.now(), index=True)


class ObstacleEvent(Base):
    __tablename__ = "obstacle_events"

    id = Column(Integer, primary_key=True, index=True)
    sensor_id = Column(String(10), nullable=False, index=True)
    zone = Column(String(50), nullable=False, index=True)
    distance_cm = Column(Float, nullable=False)
    severity = Column(String(20), nullable=False, index=True)
    event_type = Column(String(20), nullable=False)  # DETECTED, CLEARED, APPROACHING
    timestamp = Column(DateTime, default=func.now(), index=True)


class WarningEvent(Base):
    __tablename__ = "warning_events"

    id = Column(Integer, primary_key=True, index=True)
    sensor_id = Column(String(10), nullable=False, index=True)
    zone = Column(String(50), nullable=False, index=True)
    distance_cm = Column(Float, nullable=True)
    warning_level = Column(String(20), nullable=False, index=True)
    warning_message = Column(String(500), nullable=False)
    acknowledged = Column(Boolean, default=False, index=True)
    timestamp = Column(DateTime, default=func.now(), index=True)


class TrafficSignalEvent(Base):
    __tablename__ = "traffic_signal_events"

    id = Column(Integer, primary_key=True, index=True)
    signal_state = Column(String(10), nullable=False, index=True)  # RED, YELLOW, GREEN
    duration_seconds = Column(Integer, nullable=True)
    timestamp = Column(DateTime, default=func.now(), index=True)


class DeviceStatus(Base):
    __tablename__ = "device_status"

    id = Column(Integer, primary_key=True, index=True)
    device_name = Column(String(50), nullable=False, unique=True, index=True)
    device_type = Column(String(50), nullable=False)
    connection_status = Column(String(20), nullable=False, default="UNKNOWN", index=True)
    last_seen = Column(DateTime, nullable=True)
    timestamp = Column(DateTime, default=func.now())


class SystemConfig(Base):
    __tablename__ = "system_config"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(50), unique=True, index=True, nullable=False)
    value = Column(String(200), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
