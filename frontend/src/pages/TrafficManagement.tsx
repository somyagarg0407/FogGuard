// Traffic Management Page
import { useEffect, useState } from 'react';
import { TrafficCone, Clock, History } from 'lucide-react';
import { useStore } from '../store/useStore';
import { TrafficSignal } from '../components/visualization/TrafficSignal';
import { Card, StatCard, Badge } from '../components/ui';
import * as api from '../services/api';
import type { TrafficSignalEvent } from '../types';
import { formatTimestamp } from '../utils';

export function TrafficManagement() {
  const { trafficSignal } = useStore();
  const [history, setHistory] = useState<TrafficSignalEvent[]>([]);
  const [distribution, setDistribution] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      try {
        const [h, d] = await Promise.all([
          api.getTrafficHistory({ limit: 50 }),
          api.getTrafficDistribution(),
        ]);
        setHistory(h);
        setDistribution(d);
      } catch { /* silent */ }
      setLoading(false);
    };
    load();
    const interval = setInterval(load, 10000);
    return () => clearInterval(interval);
  }, []);

  const totalEvents = distribution.reduce((a, d) => a + d.count, 0);

  const stateColors: Record<string, string> = {
    RED: 'critical', GREEN: 'safe', YELLOW: 'caution'
  };

  return (
    <div className="h-full flex flex-col gap-4 p-4 overflow-y-auto">
      <div className="flex items-center gap-3">
        <TrafficCone className="w-5 h-5 text-cyan-400" />
        <h2 className="text-lg font-bold text-white">Traffic Management</h2>
        <span className="text-sm text-slate-400">— Smart traffic signal monitoring</span>
      </div>

      <div className="grid grid-cols-12 gap-4">
        {/* Traffic signal display */}
        <div className="col-span-4">
          <Card title="Current Signal" titleIcon={<TrafficCone className="w-3.5 h-3.5 text-cyan-400" />}>
            <div className="flex flex-col items-center py-6 gap-6">
              <TrafficSignal signal={trafficSignal} size="lg" />
              <div className="text-center space-y-1">
                <div className="text-xs text-slate-400 uppercase tracking-wider">Status</div>
                <div className="text-sm text-slate-300">
                  {trafficSignal
                    ? `Signal active — ${trafficSignal.duration_seconds ?? '?'}s duration`
                    : 'No signal data received'}
                </div>
              </div>
            </div>
          </Card>
        </div>

        {/* Signal stats */}
        <div className="col-span-8 space-y-4">
          <div className="grid grid-cols-3 gap-3">
            {distribution.map(d => (
              <StatCard
                key={d.state}
                label={`${d.state} Events`}
                value={d.count}
                color={d.state === 'RED' ? '#ef4444' : d.state === 'GREEN' ? '#22c55e' : '#eab308'}
                sub={`${totalEvents > 0 ? Math.round(d.count / totalEvents * 100) : 0}% of total`}
              />
            ))}
          </div>

          {/* Signal info card */}
          <Card title="Signal Information" titleIcon={<Clock className="w-3.5 h-3.5 text-cyan-400" />}>
            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <div className="text-slate-400 text-xs uppercase tracking-wider mb-1">Red Phase</div>
                <div className="text-slate-200">Stop — 30 seconds</div>
              </div>
              <div>
                <div className="text-slate-400 text-xs uppercase tracking-wider mb-1">Green Phase</div>
                <div className="text-slate-200">Go — 25 seconds</div>
              </div>
              <div>
                <div className="text-slate-400 text-xs uppercase tracking-wider mb-1">Yellow Phase</div>
                <div className="text-slate-200">Caution — 5 seconds</div>
              </div>
              <div>
                <div className="text-slate-400 text-xs uppercase tracking-wider mb-1">Hardware</div>
                <div className="text-slate-200">32=Red · 33=Yellow · 25=Green</div>
              </div>
              <div className="col-span-2 rounded border px-3 py-2 text-xs text-amber-300"
                style={{ borderColor: 'rgba(234, 179, 8, 0.25)', background: 'rgba(234, 179, 8, 0.08)' }}>
                Note: ESP32 GPIO 34 is input-only. Use GPIO 25 for the green output to drive an LED.
              </div>
            </div>
          </Card>
        </div>

        {/* Signal history */}
        <div className="col-span-12">
          <Card
            title="Signal History"
            titleIcon={<History className="w-3.5 h-3.5 text-cyan-400" />}
          >
            {loading ? (
              <p className="text-slate-500 text-center py-4">Loading...</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-left text-xs text-slate-500 uppercase tracking-wider border-b"
                      style={{ borderColor: 'rgba(13, 32, 112, 0.5)' }}>
                      <th className="pb-2 pr-4">Timestamp</th>
                      <th className="pb-2 pr-4">State</th>
                      <th className="pb-2">Duration</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y" style={{ borderColor: 'rgba(13, 32, 112, 0.3)' }}>
                    {history.map(event => (
                      <tr key={event.id} className="hover:bg-white/2">
                        <td className="py-2 pr-4 font-mono text-xs text-slate-400">
                          {formatTimestamp(event.timestamp)}
                        </td>
                        <td className="py-2 pr-4">
                          <Badge variant={(stateColors[event.signal_state] as any) ?? 'default'}>
                            {event.signal_state}
                          </Badge>
                        </td>
                        <td className="py-2 text-slate-300">
                          {event.duration_seconds ? `${event.duration_seconds}s` : '—'}
                        </td>
                      </tr>
                    ))}
                    {history.length === 0 && (
                      <tr>
                        <td colSpan={3} className="py-6 text-center text-slate-500">
                          No signal history yet. Start simulation to generate data.
                        </td>
                      </tr>
                    )}
                  </tbody>
                </table>
              </div>
            )}
          </Card>
        </div>
      </div>
    </div>
  );
}
