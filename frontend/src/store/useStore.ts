// Global state store using Zustand with high-frequency telemetry optimizations
import { create } from 'zustand';
import type { SensorReading, TrafficSignalStatus, WarningEvent, ThresholdConfig } from '../types';

export interface SystemState {
  // Connection
  wsConnected: boolean;
  backendConnected: boolean;
  simulationMode: boolean;
  simulationRunning: boolean;
  simulationScenario: string;
  dataSource: 'simulation' | 'hardware' | 'none';

  // Live data
  sensors: SensorReading[];
  trafficSignal: TrafficSignalStatus | null;
  lastUpdate: string | null;

  // Real-time Latency & Telemetry Diagnostics
  telemetryFps: number;
  backendLatencyMs: number;
  networkLatencyMs: number;
  telemetrySeq: number;
  lastPacketTime: number;

  // Warnings
  activeWarnings: WarningEvent[];
  warningHistory: WarningEvent[];
  unacknowledgedCount: number;
  muted: boolean;

  // Settings
  thresholds: ThresholdConfig;

  // Actions
  setWsConnected: (v: boolean) => void;
  setBackendConnected: (v: boolean) => void;
  setSimulationRunning: (v: boolean) => void;
  setSimulationScenario: (v: string) => void;
  updateFromTelemetry: (msg: any, rxTimeMs?: number) => void;
  acknowledgeWarning: (id: number) => void;
  acknowledgeAll: () => void;
  setMuted: (v: boolean) => void;
  setThresholds: (t: ThresholdConfig) => void;
  addWarnings: (warnings: WarningEvent[]) => void;
}

let lastRxTime = 0;
let smoothedFps = 10.0;

export const useStore = create<SystemState>((set, get) => ({
  wsConnected: false,
  backendConnected: false,
  simulationMode: true,
  simulationRunning: false,
  simulationScenario: 'normal',
  dataSource: 'none',

  sensors: [],
  trafficSignal: null,
  lastUpdate: null,

  telemetryFps: 10.0,
  backendLatencyMs: 0.5,
  networkLatencyMs: 1.0,
  telemetrySeq: 0,
  lastPacketTime: 0,

  activeWarnings: [],
  warningHistory: [],
  unacknowledgedCount: 0,
  muted: false,

  thresholds: {
    critical_cm: 50,
    warning_cm: 100,
    caution_cm: 150,
    max_range_cm: 400,
  },

  setWsConnected: (v) => set({ wsConnected: v }),
  setBackendConnected: (v) => set({ backendConnected: v }),
  setSimulationRunning: (v) => set({ simulationRunning: v }),
  setSimulationScenario: (v) => set({ simulationScenario: v }),

  updateFromTelemetry: (msg, rxTimeMs) => {
    if (msg.type !== 'telemetry') return;

    const now = rxTimeMs || performance.now();
    if (lastRxTime > 0) {
      const dt = (now - lastRxTime) / 1000.0;
      if (dt > 0.005 && dt < 2.0) {
        const instantFps = 1.0 / dt;
        smoothedFps = smoothedFps * 0.85 + instantFps * 0.15;
      }
    }
    lastRxTime = now;

    // Extract latency metrics
    const perf = msg.perf || {};
    const backendProc = perf.backend_proc_ms ?? 0.5;
    let netLatency = 1.0;
    if (perf.host_tx_ms) {
      netLatency = Math.max(0.1, Date.now() - perf.host_tx_ms);
    }

    const newWarnings: WarningEvent[] = msg.new_warnings || [];
    let allWarnings = get().activeWarnings;
    let unackCount = get().unacknowledgedCount;

    // Only modify warnings array when new warnings actually arrive
    if (newWarnings.length > 0) {
      allWarnings = [
        ...newWarnings,
        ...allWarnings.filter((w) => !newWarnings.find((n) => n.id === w.id)),
      ].slice(0, 100);
      unackCount = allWarnings.filter((w) => !w.acknowledged).length;
    }

    set({
      sensors: msg.sensors || [],
      trafficSignal: msg.traffic_signal,
      lastUpdate: msg.timestamp,
      simulationMode: msg.simulation_mode,
      dataSource: msg.source,
      telemetryFps: Math.round(smoothedFps * 10) / 10,
      backendLatencyMs: backendProc,
      networkLatencyMs: Math.round(netLatency * 10) / 10,
      telemetrySeq: perf.seq ?? (get().telemetrySeq + 1),
      lastPacketTime: now,
      activeWarnings: allWarnings,
      unacknowledgedCount: unackCount,
    });
  },

  acknowledgeWarning: (id) => {
    set((state) => {
      const updated = state.activeWarnings.map((w) =>
        w.id === id ? { ...w, acknowledged: true } : w
      );
      return {
        activeWarnings: updated,
        unacknowledgedCount: updated.filter((w) => !w.acknowledged).length,
      };
    });
  },

  acknowledgeAll: () => {
    set((state) => ({
      activeWarnings: state.activeWarnings.map((w) => ({ ...w, acknowledged: true })),
      unacknowledgedCount: 0,
    }));
  },

  setMuted: (v) => set({ muted: v }),
  setThresholds: (t) => set({ thresholds: t }),
  addWarnings: (warnings) => set((s) => ({ activeWarnings: [...warnings, ...s.activeWarnings] })),
}));
