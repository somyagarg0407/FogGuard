// Analytics Page
import { useEffect, useState } from 'react';
import { BarChart3, TrendingUp, AlertTriangle, Radio, RefreshCw, ShieldAlert } from 'lucide-react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer,
  PieChart, Pie, Cell, LineChart, Line, CartesianGrid, Legend
} from 'recharts';
import { Card, StatCard, Spinner, Badge } from '../components/ui';
import * as api from '../services/api';
import type { AnalyticsSummary } from '../types';
import { ZONE_DISPLAY } from '../types';

const COLORS = {
  CRITICAL: '#ef4444',
  WARNING: '#f97316',
  CAUTION: '#eab308',
  SAFE: '#22c55e',
  RED: '#ef4444',
  GREEN: '#22c55e',
  YELLOW: '#eab308',
};

const SENSOR_COLORS = ['#22d3ee', '#3b82f6', '#8b5cf6', '#ec4899', '#f97316', '#22c55e'];

export function Analytics() {
  const [summary, setSummary] = useState<AnalyticsSummary | null>(null);
  const [obstaclesOverTime, setObstaclesOverTime] = useState<any[]>([]);
  const [warningsOverTime, setWarningsOverTime] = useState<any[]>([]);
  const [trafficDist, setTrafficDist] = useState<any[]>([]);
  const [sensorHeatmap, setSensorHeatmap] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [s, ot, wt, td, sh] = await Promise.all([
        api.getAnalyticsSummary(),
        api.getObstaclesOverTime(),
        api.getWarningsOverTime(),
        api.getTrafficDistribution(),
        api.getSensorHeatmap(),
      ]);
      setSummary(s);
      setObstaclesOverTime(ot);
      setWarningsOverTime(wt);
      setTrafficDist(td);
      setSensorHeatmap(sh);
    } catch { /* silent */ }
    setLoading(false);
  };

  useEffect(() => { load(); }, []);

  // Transform heatmap data for bar chart
  const sensorBarData = Object.entries(summary?.sensor_distribution ?? {}).map(([id, count]) => ({
    name: id,
    count,
  }));

  // Group warnings over time by level for stacked chart
  const warningChartData = (() => {
    const byTime: Record<string, any> = {};
    for (const row of warningsOverTime) {
      if (!byTime[row.time]) byTime[row.time] = { time: row.time };
      byTime[row.time][row.level] = row.count;
    }
    return Object.values(byTime).slice(-24);
  })();

  const tooltipStyle = {
    backgroundColor: '#060f2e',
    border: '1px solid rgba(13, 32, 112, 0.5)',
    borderRadius: 8,
    color: '#e2e8f0',
  };

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <BarChart3 className="w-5 h-5 text-cyan-400" />
          <h2 className="text-lg font-bold text-white">Analytics</h2>
          <span className="text-sm text-slate-400">— Database-derived insights</span>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 text-sm text-slate-400 hover:text-cyan-400 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Summary stats */}
      <div className="grid grid-cols-5 gap-3">
        <StatCard
          label="Total Detections"
          value={summary?.total_obstacle_detections ?? '—'}
          icon={<Radio className="w-4 h-4" />}
          color="#22d3ee"
        />
        <StatCard
          label="Total Warnings"
          value={summary?.total_warning_events ?? '—'}
          icon={<AlertTriangle className="w-4 h-4" />}
          color="#f97316"
        />
        <StatCard
          label="Critical Warnings"
          value={summary?.critical_warnings ?? '—'}
          icon={<AlertTriangle className="w-4 h-4" />}
          color="#ef4444"
        />
        <StatCard
          label="Min Distance"
          value={summary?.min_obstacle_distance_cm != null ? `${Math.round(summary.min_obstacle_distance_cm)} cm` : '—'}
          icon={<TrendingUp className="w-4 h-4" />}
          color="#eab308"
        />
        <StatCard
          label="Traffic Events"
          value={summary?.total_traffic_signal_events ?? '—'}
          icon={<BarChart3 className="w-4 h-4" />}
          color="#8b5cf6"
          sub={summary?.most_frequent_zone
            ? `Top zone: ${ZONE_DISPLAY[summary.most_frequent_zone as keyof typeof ZONE_DISPLAY] ?? summary.most_frequent_zone}`
            : undefined}
        />
      </div>

      {/* Charts row 1 */}
      <div className="grid grid-cols-12 gap-4">
        {/* Obstacles over time */}
        <Card title="Obstacle Detections Over Time"
          titleIcon={<Radio className="w-3.5 h-3.5 text-cyan-400" />}
          className="col-span-8">
          {loading ? (
            <div className="flex items-center justify-center h-40"><Spinner size={32} /></div>
          ) : obstaclesOverTime.length === 0 ? (
            <div className="flex items-center justify-center h-40 text-slate-500">No data yet</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <LineChart data={obstaclesOverTime}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(13,32,112,0.5)" />
                <XAxis dataKey="time" tick={{ fill: '#94a3b8', fontSize: 10 }}
                  tickFormatter={v => v?.split(' ')[1] || v} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Line type="monotone" dataKey="count" stroke="#22d3ee" strokeWidth={2}
                  dot={false} name="Detections" />
              </LineChart>
            </ResponsiveContainer>
          )}
        </Card>

        {/* Traffic distribution */}
        <Card title="Traffic Signal Distribution"
          titleIcon={<BarChart3 className="w-3.5 h-3.5 text-cyan-400" />}
          className="col-span-4">
          {loading ? (
            <div className="flex items-center justify-center h-40"><Spinner size={32} /></div>
          ) : trafficDist.length === 0 ? (
            <div className="flex items-center justify-center h-40 text-slate-500">No data</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={trafficDist} dataKey="count" nameKey="state" cx="50%" cy="50%"
                  outerRadius={70} label={({ name, percent }: any) => `${name ?? ''} ${(((percent as number) ?? 0) * 100).toFixed(0)}%`}
                  labelLine={false}>
                  {trafficDist.map((entry, i) => (
                    <Cell key={i} fill={COLORS[entry.state as keyof typeof COLORS] ?? '#94a3b8'} />
                  ))}
                </Pie>
                <Tooltip contentStyle={tooltipStyle} />
              </PieChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      {/* Charts row 2 */}
      <div className="grid grid-cols-12 gap-4">
        {/* Sensor detection distribution */}
        <Card title="Sensor Detection Distribution"
          titleIcon={<Radio className="w-3.5 h-3.5 text-cyan-400" />}
          className="col-span-6">
          {loading ? (
            <div className="flex items-center justify-center h-40"><Spinner size={32} /></div>
          ) : sensorBarData.length === 0 ? (
            <div className="flex items-center justify-center h-40 text-slate-500">No data yet</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={sensorBarData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(13,32,112,0.5)" />
                <XAxis dataKey="name" tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 11 }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Bar dataKey="count" name="Detections" radius={[4, 4, 0, 0]}>
                  {sensorBarData.map((_, i) => (
                    <Cell key={i} fill={SENSOR_COLORS[i % SENSOR_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>

        {/* Warnings over time stacked */}
        <Card title="Warning Frequency Over Time"
          titleIcon={<AlertTriangle className="w-3.5 h-3.5 text-red-400" />}
          className="col-span-6">
          {loading ? (
            <div className="flex items-center justify-center h-40"><Spinner size={32} /></div>
          ) : warningChartData.length === 0 ? (
            <div className="flex items-center justify-center h-40 text-slate-500">No data yet</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={warningChartData}>
                <CartesianGrid strokeDasharray="3 3" stroke="rgba(13,32,112,0.5)" />
                <XAxis dataKey="time" tick={{ fill: '#94a3b8', fontSize: 9 }}
                  tickFormatter={v => v?.split(' ')[1] || v} />
                <YAxis tick={{ fill: '#94a3b8', fontSize: 10 }} />
                <Tooltip contentStyle={tooltipStyle} />
                <Legend wrapperStyle={{ fontSize: 10, color: '#94a3b8' }} />
                <Bar dataKey="CRITICAL" stackId="a" fill="#ef4444" radius={0} />
                <Bar dataKey="WARNING" stackId="a" fill="#f97316" radius={0} />
                <Bar dataKey="CAUTION" stackId="a" fill="#eab308" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          )}
        </Card>
      </div>

      {/* Sensor Severity Breakdown from sensorHeatmap */}
      <Card title="Sensor Severity Breakdown" titleIcon={<ShieldAlert className="w-3.5 h-3.5 text-cyan-400" />}>
        {loading ? (
          <div className="flex items-center justify-center h-24"><Spinner size={24} /></div>
        ) : sensorHeatmap.length === 0 ? (
          <p className="text-slate-500 text-sm text-center py-4">No sensor events recorded yet.</p>
        ) : (
          <div className="grid grid-cols-3 gap-3">
            {sensorHeatmap.map((item, idx) => (
              <div
                key={idx}
                className="flex items-center justify-between p-2.5 rounded-lg border"
                style={{ background: 'rgba(2, 8, 24, 0.4)', borderColor: 'rgba(13, 32, 112, 0.5)' }}
              >
                <div className="flex items-center gap-2">
                  <span className="font-mono text-cyan-400 font-bold text-sm">{item.sensor_id}</span>
                  <Badge variant={item.severity === 'CRITICAL' ? 'critical' : item.severity === 'WARNING' ? 'warning' : 'caution'}>
                    {item.severity}
                  </Badge>
                </div>
                <span className="font-mono text-sm text-slate-200">{item.count} events</span>
              </div>
            ))}
          </div>
        )}
      </Card>
    </div>
  );
}
