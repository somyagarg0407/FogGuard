// API service layer — all backend REST calls
import type {
  AnalyticsSummary, DeviceStatus, ObstacleEvent,
  TrafficSignalEvent, WarningEvent, ThresholdConfig, SimulationScenario
} from '../types';

const BASE = '/api/v1';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  });
  if (!res.ok) {
    const err = await res.text();
    throw new Error(`API Error ${res.status}: ${err}`);
  }
  return res.json();
}

// ── Sensor ────────────────────────────────────────────────────────────────────
export const getLatestSensors = () => request<any>('/sensors/latest');
export const getSensorHistory = (params?: { sensor_id?: string; limit?: number; offset?: number }) => {
  const q = new URLSearchParams();
  if (params?.sensor_id) q.set('sensor_id', params.sensor_id);
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.offset) q.set('offset', String(params.offset));
  return request<any[]>(`/sensors/history?${q}`);
};

// ── Obstacles ─────────────────────────────────────────────────────────────────
export const getObstacles = (params?: {
  sensor_id?: string; zone?: string; severity?: string;
  start_time?: string; end_time?: string; limit?: number; offset?: number;
}) => {
  const q = new URLSearchParams();
  if (params?.sensor_id) q.set('sensor_id', params.sensor_id);
  if (params?.zone) q.set('zone', params.zone);
  if (params?.severity) q.set('severity', params.severity);
  if (params?.start_time) q.set('start_time', params.start_time);
  if (params?.end_time) q.set('end_time', params.end_time);
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.offset) q.set('offset', String(params.offset));
  return request<ObstacleEvent[]>(`/obstacles?${q}`);
};

// ── Warnings ──────────────────────────────────────────────────────────────────
export const getWarnings = (params?: {
  sensor_id?: string; zone?: string; warning_level?: string;
  acknowledged?: boolean; limit?: number; offset?: number;
}) => {
  const q = new URLSearchParams();
  if (params?.sensor_id) q.set('sensor_id', params.sensor_id);
  if (params?.zone) q.set('zone', params.zone);
  if (params?.warning_level) q.set('warning_level', params.warning_level);
  if (params?.acknowledged !== undefined) q.set('acknowledged', String(params.acknowledged));
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.offset) q.set('offset', String(params.offset));
  return request<WarningEvent[]>(`/warnings?${q}`);
};

export const acknowledgeWarning = (id: number) =>
  request('/warnings/acknowledge', { method: 'POST', body: JSON.stringify({ warning_id: id }) });

export const acknowledgeAllWarnings = () =>
  request('/warnings/acknowledge-all', { method: 'POST' });

// ── Traffic ───────────────────────────────────────────────────────────────────
export const getTrafficStatus = () => request<any>('/traffic/status');
export const getTrafficHistory = (params?: { limit?: number; offset?: number }) => {
  const q = new URLSearchParams();
  if (params?.limit) q.set('limit', String(params.limit));
  if (params?.offset) q.set('offset', String(params.offset));
  return request<TrafficSignalEvent[]>(`/traffic/history?${q}`);
};

// ── Analytics ─────────────────────────────────────────────────────────────────
export const getAnalyticsSummary = () => request<AnalyticsSummary>('/analytics/summary');
export const getObstaclesOverTime = () => request<any[]>('/analytics/obstacles-over-time');
export const getWarningsOverTime = () => request<any[]>('/analytics/warnings-over-time');
export const getTrafficDistribution = () => request<any[]>('/analytics/traffic-distribution');
export const getSensorHeatmap = () => request<any[]>('/analytics/sensor-heatmap');

// ── Devices ───────────────────────────────────────────────────────────────────
export const getDeviceStatuses = () => request<DeviceStatus[]>('/devices/status');
export const getSystemInfo = () => request<any>('/devices/system-info');

// ── Simulation ────────────────────────────────────────────────────────────────
export const getSimulationStatus = () => request<any>('/simulation/status');
export const getSimulationScenarios = () => request<{ scenarios: SimulationScenario[] }>('/simulation/scenarios');

export const controlSimulation = (action: string, scenario?: string, speed?: number) =>
  request('/simulation/control', {
    method: 'POST',
    body: JSON.stringify({ action, scenario, speed_multiplier: speed }),
  });

// ── Settings ──────────────────────────────────────────────────────────────────
export const getThresholds = () => request<ThresholdConfig>('/settings/thresholds');
export const updateThresholds = (config: ThresholdConfig) =>
  request('/settings/thresholds', { method: 'POST', body: JSON.stringify(config) });

// ── IoT Telemetry ─────────────────────────────────────────────────────────────
export const postTelemetry = (payload: any) =>
  request('/iot/telemetry', { method: 'POST', body: JSON.stringify(payload) });

// ── Export CSV ────────────────────────────────────────────────────────────────
export function exportToCSV(data: any[], filename: string) {
  if (!data.length) return;
  const headers = Object.keys(data[0]);
  const rows = data.map(row => headers.map(h => JSON.stringify(row[h] ?? '')).join(','));
  const csv = [headers.join(','), ...rows].join('\n');
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
