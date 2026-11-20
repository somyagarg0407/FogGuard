
import { Activity, AlertTriangle, Maximize2, Radio, Shield } from 'lucide-react';
import { useStore } from '../store/useStore';
import { ObstacleVisualization } from '../components/visualization/ObstacleVisualization';
import { TrafficSignal } from '../components/visualization/TrafficSignal';
import { Card, StatCard, SensorRow, WarningCard, Button } from '../components/ui';
import { SimulationControl } from './Dashboard/SimulationControl';
import * as api from '../services/api';

export function Dashboard() {
  const {
    sensors, trafficSignal, activeWarnings, unacknowledgedCount,
    acknowledgeWarning, acknowledgeAll
  } = useStore();

  const obstacleCount = sensors.filter(s => s.obstacle_detected).length;

  const nearestDistance = sensors
    .filter(s => s.obstacle_detected && s.distance_cm !== null)
    .sort((a, b) => (a.distance_cm ?? 999) - (b.distance_cm ?? 999))[0];

  const dangerZone = sensors
    .filter(s => s.obstacle_detected)
    .sort((a, b) => {
      const order: Record<string, number> = {
        CRITICAL: 0, WARNING: 1, CAUTION: 2
      };
      return (order[a.warning_level] ?? 3) - (order[b.warning_level] ?? 3);
    })[0];

  const handleAck = async (id: number) => {
    acknowledgeWarning(id);
    try { await api.acknowledgeWarning(id); } catch { /* silent */ }
  };

  const handleAckAll = async () => {
    acknowledgeAll();
    try { await api.acknowledgeAllWarnings(); } catch { /* silent */ }
  };

  const unackWarnings = activeWarnings
    .filter(w => !w.acknowledged)
    .slice(0, 5);

  return (
    <div className="dashboard-layout h-full">

      {/* KPI ROW */}
      <div className="dashboard-kpis">
        <StatCard
          label="Active Obstacles"
          value={obstacleCount}
          icon={<Radio className="w-4 h-4" />}
          color={obstacleCount > 0 ? '#f97316' : '#22c55e'}
        />

        <StatCard
          label="Nearest Obstacle"
          value={nearestDistance
            ? `${Math.round(nearestDistance.distance_cm!)} cm`
            : 'CLEAR'}
          icon={<Maximize2 className="w-4 h-4" />}
          color={nearestDistance ? '#ef4444' : '#22c55e'}
          sub={nearestDistance
            ? `${nearestDistance.sensor_id} · ${nearestDistance.warning_level}`
            : 'All zones clear'}
        />

        <StatCard
          label="Active Warnings"
          value={unacknowledgedCount}
          icon={<AlertTriangle className="w-4 h-4" />}
          color={unacknowledgedCount > 0 ? '#ef4444' : '#22c55e'}
        />

        <StatCard
          label="Danger Zone"
          value={dangerZone ? dangerZone.zone.replace(/_/g, ' ').toUpperCase() : 'NONE'}
          icon={<Shield className="w-4 h-4" />}
          color={dangerZone ? '#f97316' : '#22c55e'}
          sub={dangerZone ? dangerZone.sensor_id : 'All safe'}
        />
      </div>

      {/* MAIN CONTENT */}
      <div className="dashboard-main">

        {/* 3D VIEW - 75% */}
        <section className="dashboard-visualization">
          <ObstacleVisualization sensors={sensors} />
        </section>

        {/* RIGHT PANEL - 25% */}
        <aside className="dashboard-right">

          <Card
            title="Sensor Status"
            titleIcon={<Radio className="w-3.5 h-3.5 text-cyan-400" />}
            className="dashboard-sensor-card"
          >
            <div className="flex flex-col gap-0.5">
              {sensors.length === 0 ? (
                <p className="text-sm text-slate-500 text-center py-3">
                  No sensor data
                </p>
              ) : (
                sensors.map(s => (
                  <SensorRow key={s.sensor_id} sensor={s} />
                ))
              )}
            </div>
          </Card>

          <Card
            title="Traffic Signal"
            titleIcon={<Activity className="w-3.5 h-3.5 text-cyan-400" />}
            className="dashboard-traffic-card"
          >
            <TrafficSignal signal={trafficSignal} size="sm" />
          </Card>

          <Card
            title={`Warnings (${unacknowledgedCount} unread)`}
            titleIcon={<AlertTriangle className="w-3.5 h-3.5 text-red-400" />}
            headerRight={
              unacknowledgedCount > 0 ? (
                <Button variant="ghost" size="sm" onClick={handleAckAll}>
                  Ack All
                </Button>
              ) : undefined
            }
            className="dashboard-warning-card"
          >
            <div className="space-y-2 overflow-y-auto">
              {unackWarnings.length === 0 ? (
                <p className="text-sm text-slate-500 text-center py-1">
                  No active warnings
                </p>
              ) : (
                unackWarnings.map(w => (
                  <WarningCard key={w.id} warning={w} onAck={handleAck} />
                ))
              )}
            </div>
          </Card>

        </aside>
      </div>

      {/* SIMULATION CONTROL */}
      <SimulationControl />
    </div>
  );
}
