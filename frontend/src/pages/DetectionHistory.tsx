// Detection History Page
import { useEffect, useState, useCallback } from 'react';
import { History, Search, Download, Filter, ChevronLeft, ChevronRight } from 'lucide-react';
import { Card, Badge, Button, Spinner } from '../components/ui';
import * as api from '../services/api';
import type { ObstacleEvent, WarningEvent, TrafficSignalEvent } from '../types';
import { formatTimestamp } from '../utils';

const TABS = ['Obstacles', 'Warnings', 'Traffic'] as const;
type Tab = typeof TABS[number];

const PAGE_SIZE = 20;

const SEVERITY_VARIANTS: Record<string, any> = {
  CRITICAL: 'critical', WARNING: 'warning', CAUTION: 'caution', SAFE: 'safe'
};
const TRAFFIC_VARIANTS: Record<string, any> = {
  RED: 'critical', GREEN: 'safe', YELLOW: 'caution'
};

export function DetectionHistory() {
  const [tab, setTab] = useState<Tab>('Obstacles');
  const [obstacles, setObstacles] = useState<ObstacleEvent[]>([]);
  const [warnings, setWarnings] = useState<WarningEvent[]>([]);
  const [traffic, setTraffic] = useState<TrafficSignalEvent[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState(0);
  const [filters, setFilters] = useState({ sensor_id: '', zone: '', severity: '' });
  const [search, setSearch] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const offset = page * PAGE_SIZE;
      if (tab === 'Obstacles') {
        const data = await api.getObstacles({
          sensor_id: filters.sensor_id || undefined,
          zone: filters.zone || undefined,
          severity: filters.severity || undefined,
          limit: PAGE_SIZE,
          offset,
        });
        setObstacles(data);
      } else if (tab === 'Warnings') {
        const data = await api.getWarnings({
          sensor_id: filters.sensor_id || undefined,
          warning_level: filters.severity || undefined,
          limit: PAGE_SIZE,
          offset,
        });
        setWarnings(data);
      } else {
        const data = await api.getTrafficHistory({ limit: PAGE_SIZE, offset });
        setTraffic(data);
      }
    } catch { /* silent */ }
    setLoading(false);
  }, [tab, page, filters]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { setPage(0); }, [tab, filters]);

  const handleExport = () => {
    if (tab === 'Obstacles') api.exportToCSV(obstacles, 'obstacles.csv');
    else if (tab === 'Warnings') api.exportToCSV(warnings, 'warnings.csv');
    else api.exportToCSV(traffic, 'traffic.csv');
  };

  const filterRow = (item: any): boolean => {
    if (!search) return true;
    const s = search.toLowerCase();
    return Object.values(item).some(v => String(v).toLowerCase().includes(s));
  };

  return (
    <div className="h-full flex flex-col p-4 gap-4 overflow-hidden">
      <div className="flex items-center justify-between flex-shrink-0">
        <div className="flex items-center gap-3">
          <History className="w-5 h-5 text-cyan-400" />
          <h2 className="text-lg font-bold text-white">Detection History</h2>
        </div>
        <Button variant="ghost" size="sm" onClick={handleExport}>
          <Download className="w-3.5 h-3.5" />
          Export CSV
        </Button>
      </div>

      {/* Tabs */}
      <div className="flex gap-2 flex-shrink-0">
        {TABS.map(t => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-all ${
              tab === t
                ? 'bg-cyan-400/10 text-cyan-400 border border-cyan-400/20'
                : 'text-slate-400 hover:text-slate-200 hover:bg-white/5 border border-transparent'
            }`}
          >
            {t}
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="flex items-center gap-3 flex-shrink-0">
        <div className="relative">
          <Search className="w-3.5 h-3.5 absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search..."
            className="pl-8 pr-3 py-1.5 text-sm rounded-lg border bg-transparent text-slate-200 w-48"
            style={{ borderColor: 'rgba(13, 32, 112, 0.8)', background: 'rgba(2, 8, 24, 0.5)' }}
          />
        </div>

        <Filter className="w-3.5 h-3.5 text-slate-500" />

        {tab !== 'Traffic' && (
          <>
            <select
              value={filters.sensor_id}
              onChange={e => setFilters(f => ({ ...f, sensor_id: e.target.value }))}
              className="px-3 py-1.5 text-sm rounded-lg border bg-transparent text-slate-200"
              style={{ borderColor: 'rgba(13, 32, 112, 0.8)', background: 'rgba(2, 8, 24, 0.5)' }}
            >
              <option value="" style={{ background: '#060f2e' }}>All Sensors</option>
              {['S1', 'S2', 'S3', 'S4', 'S5', 'S6'].map(s => (
                <option key={s} value={s} style={{ background: '#060f2e' }}>{s}</option>
              ))}
            </select>

            <select
              value={filters.severity}
              onChange={e => setFilters(f => ({ ...f, severity: e.target.value }))}
              className="px-3 py-1.5 text-sm rounded-lg border bg-transparent text-slate-200"
              style={{ borderColor: 'rgba(13, 32, 112, 0.8)', background: 'rgba(2, 8, 24, 0.5)' }}
            >
              <option value="" style={{ background: '#060f2e' }}>All Levels</option>
              {['CRITICAL', 'WARNING', 'CAUTION', 'SAFE'].map(l => (
                <option key={l} value={l} style={{ background: '#060f2e' }}>{l}</option>
              ))}
            </select>
          </>
        )}
      </div>

      {/* Table */}
      <Card className="flex-1 overflow-hidden" title="" titleIcon={undefined}>
        {loading ? (
          <div className="flex items-center justify-center h-40"><Spinner size={32} /></div>
        ) : (
          <div className="overflow-auto h-full">
            {tab === 'Obstacles' && (
              <table className="w-full text-sm">
                <thead className="sticky top-0" style={{ background: 'rgba(6, 15, 46, 0.95)' }}>
                  <tr className="text-left text-xs text-slate-500 uppercase tracking-wider border-b"
                    style={{ borderColor: 'rgba(13, 32, 112, 0.5)' }}>
                    <th className="pb-2 pr-4">ID</th>
                    <th className="pb-2 pr-4">Sensor</th>
                    <th className="pb-2 pr-4">Zone</th>
                    <th className="pb-2 pr-4">Distance</th>
                    <th className="pb-2 pr-4">Severity</th>
                    <th className="pb-2 pr-4">Type</th>
                    <th className="pb-2">Timestamp</th>
                  </tr>
                </thead>
                <tbody>
                  {obstacles.filter(filterRow).map(e => (
                    <tr key={e.id} className="border-b hover:bg-white/2"
                      style={{ borderColor: 'rgba(13, 32, 112, 0.2)' }}>
                      <td className="py-2 pr-4 font-mono text-xs text-slate-500">{e.id}</td>
                      <td className="py-2 pr-4 font-mono font-semibold">{e.sensor_id}</td>
                      <td className="py-2 pr-4 text-slate-400 text-xs">{e.zone.replace(/_/g, ' ')}</td>
                      <td className="py-2 pr-4 font-mono">{e.distance_cm} cm</td>
                      <td className="py-2 pr-4"><Badge variant={SEVERITY_VARIANTS[e.severity]}>{e.severity}</Badge></td>
                      <td className="py-2 pr-4 text-slate-400 text-xs">{e.event_type}</td>
                      <td className="py-2 font-mono text-xs text-slate-400">{formatTimestamp(e.timestamp)}</td>
                    </tr>
                  ))}
                  {obstacles.length === 0 && (
                    <tr><td colSpan={7} className="py-8 text-center text-slate-500">No obstacle events recorded</td></tr>
                  )}
                </tbody>
              </table>
            )}

            {tab === 'Warnings' && (
              <table className="w-full text-sm">
                <thead className="sticky top-0" style={{ background: 'rgba(6, 15, 46, 0.95)' }}>
                  <tr className="text-left text-xs text-slate-500 uppercase tracking-wider border-b"
                    style={{ borderColor: 'rgba(13, 32, 112, 0.5)' }}>
                    <th className="pb-2 pr-4">ID</th>
                    <th className="pb-2 pr-4">Sensor</th>
                    <th className="pb-2 pr-4">Level</th>
                    <th className="pb-2 pr-4">Message</th>
                    <th className="pb-2 pr-4">Ack</th>
                    <th className="pb-2">Timestamp</th>
                  </tr>
                </thead>
                <tbody>
                  {warnings.filter(filterRow).map(w => (
                    <tr key={w.id} className="border-b hover:bg-white/2"
                      style={{ borderColor: 'rgba(13, 32, 112, 0.2)' }}>
                      <td className="py-2 pr-4 font-mono text-xs text-slate-500">{w.id}</td>
                      <td className="py-2 pr-4 font-mono font-semibold">{w.sensor_id}</td>
                      <td className="py-2 pr-4"><Badge variant={SEVERITY_VARIANTS[w.warning_level]}>{w.warning_level}</Badge></td>
                      <td className="py-2 pr-4 text-slate-300 text-xs max-w-xs truncate">{w.warning_message}</td>
                      <td className="py-2 pr-4">
                        <Badge variant={w.acknowledged ? 'safe' : 'default'}>{w.acknowledged ? 'Yes' : 'No'}</Badge>
                      </td>
                      <td className="py-2 font-mono text-xs text-slate-400">{formatTimestamp(w.timestamp)}</td>
                    </tr>
                  ))}
                  {warnings.length === 0 && (
                    <tr><td colSpan={6} className="py-8 text-center text-slate-500">No warnings recorded</td></tr>
                  )}
                </tbody>
              </table>
            )}

            {tab === 'Traffic' && (
              <table className="w-full text-sm">
                <thead className="sticky top-0" style={{ background: 'rgba(6, 15, 46, 0.95)' }}>
                  <tr className="text-left text-xs text-slate-500 uppercase tracking-wider border-b"
                    style={{ borderColor: 'rgba(13, 32, 112, 0.5)' }}>
                    <th className="pb-2 pr-4">ID</th>
                    <th className="pb-2 pr-4">State</th>
                    <th className="pb-2 pr-4">Duration</th>
                    <th className="pb-2">Timestamp</th>
                  </tr>
                </thead>
                <tbody>
                  {traffic.filter(filterRow).map(e => (
                    <tr key={e.id} className="border-b hover:bg-white/2"
                      style={{ borderColor: 'rgba(13, 32, 112, 0.2)' }}>
                      <td className="py-2 pr-4 font-mono text-xs text-slate-500">{e.id}</td>
                      <td className="py-2 pr-4"><Badge variant={TRAFFIC_VARIANTS[e.signal_state]}>{e.signal_state}</Badge></td>
                      <td className="py-2 pr-4 text-slate-300">{e.duration_seconds ? `${e.duration_seconds}s` : '—'}</td>
                      <td className="py-2 font-mono text-xs text-slate-400">{formatTimestamp(e.timestamp)}</td>
                    </tr>
                  ))}
                  {traffic.length === 0 && (
                    <tr><td colSpan={4} className="py-8 text-center text-slate-500">No traffic events recorded</td></tr>
                  )}
                </tbody>
              </table>
            )}
          </div>
        )}
      </Card>

      {/* Pagination */}
      <div className="flex items-center justify-between flex-shrink-0">
        <span className="text-xs text-slate-500">Page {page + 1}</span>
        <div className="flex gap-2">
          <Button variant="ghost" size="sm" onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}>
            <ChevronLeft className="w-3.5 h-3.5" />
          </Button>
          <Button variant="ghost" size="sm" onClick={() => setPage(p => p + 1)}>
            <ChevronRight className="w-3.5 h-3.5" />
          </Button>
        </div>
      </div>
    </div>
  );
}
