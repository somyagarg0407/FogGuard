// Core TypeScript types for FogGuard

export type WarningLevel = 'SAFE' | 'CAUTION' | 'WARNING' | 'CRITICAL' | 'CLEAR';
export type TrafficState = 'RED' | 'YELLOW' | 'GREEN' | 'UNKNOWN';
export type ConnectionStatus = 'CONNECTED' | 'DISCONNECTED' | 'SIMULATED' | 'UNKNOWN' | 'ERROR';

export type SensorZone =
  | 'front_left'
  | 'front_center'
  | 'front_center_left'
  | 'front_center_right'
  | 'front_right'
  | 'left_side'
  | 'right_side'
  | 'roof_center';

export interface SensorReading {
  sensor_id: string;
  zone: SensorZone;
  distance_cm: number | null;
  obstacle_detected: boolean;
  warning_level: WarningLevel;
}

export interface TrafficSignalStatus {
  state: TrafficState;
  duration_seconds: number | null;
}

export interface TelemetryPerf {
  seq?: number;
  uptime_ms?: number;
  backend_proc_ms?: number;
  host_tx_ms?: number;
}

export interface TelemetryMessage {
  type: 'telemetry' | 'ping';
  source: 'simulation' | 'hardware' | 'none';
  timestamp: string;
  sensors: SensorReading[];
  traffic_signal: TrafficSignalStatus | null;
  new_warnings: WarningEvent[];
  simulation_mode: boolean;
  perf?: TelemetryPerf;
}

export interface WarningEvent {
  id: number;
  sensor_id: string;
  zone: string;
  distance_cm: number | null;
  warning_level: WarningLevel;
  warning_message: string;
  acknowledged: boolean;
  timestamp: string;
}

export interface ObstacleEvent {
  id: number;
  sensor_id: string;
  zone: string;
  distance_cm: number;
  severity: WarningLevel;
  event_type: string;
  timestamp: string;
}

export interface TrafficSignalEvent {
  id: number;
  signal_state: TrafficState;
  duration_seconds: number | null;
  timestamp: string;
}

export interface DeviceStatus {
  id: number;
  device_name: string;
  device_type: string;
  connection_status: ConnectionStatus;
  last_seen: string | null;
  timestamp: string | null;
}

export interface AnalyticsSummary {
  total_obstacle_detections: number;
  total_warning_events: number;
  critical_warnings: number;
  most_frequent_zone: string | null;
  min_obstacle_distance_cm: number | null;
  sensor_distribution: Record<string, number>;
  total_traffic_signal_events: number;
}

export interface SimulationScenario {
  id: string;
  name: string;
}

export interface ThresholdConfig {
  critical_cm: number;
  warning_cm: number;
  caution_cm: number;
  max_range_cm: number;
}

export const ZONE_DISPLAY: Record<SensorZone, string> = {
  front_left: 'Front Left',
  front_center: 'Front Center',
  front_center_left: 'Front Center Left',
  front_center_right: 'Front Center Right',
  front_right: 'Front Right',
  left_side: 'Left Side',
  right_side: 'Right Side',
  roof_center: 'Roof Center',
};

export const SENSOR_IDS = ['S1', 'S2', 'S3', 'S4', 'S5', 'S6'] as const;
export type SensorId = typeof SENSOR_IDS[number];

export const SENSOR_ZONE_MAP: Record<SensorId, SensorZone> = {
  S1: 'front_left',
  S2: 'front_center_left',
  S3: 'front_center_right',
  S4: 'front_right',
  S5: 'left_side',
  S6: 'right_side',
};
