// Device Status Page
import { useEffect, useState, type ReactNode } from 'react';
import { Cpu, RefreshCw, Wifi, Bluetooth, Radio, TrafficCone } from 'lucide-react';
import { Card, StatCard, StatusDot, Spinner } from '../components/ui';
import * as api from '../services/api';
import { formatTimeAgo } from '../utils';

const DEVICE_ICONS: Record<string, ReactNode> = {
  'ESP32': <Wifi className="w-5 h-5" />,
  'Arduino': <Cpu className="w-5 h-5" />,
  'Ultrasonic Sensor': <Radio className="w-4 h-4" />,
  'Traffic Signal': <TrafficCone className="w-4 h-4" />,
};

export function DeviceStatus() {
  const [devices, setDevices] = useState<any[]>([]);
  const [sysInfo, setSysInfo] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  const load = async () => {
    setLoading(true);
    try {
      const [d, s] = await Promise.all([api.getDeviceStatuses(), api.getSystemInfo()]);
      setDevices(d);
      setSysInfo(s);
    } catch { /* silent */ }
    setLoading(false);
  };

  useEffect(() => { load(); const t = setInterval(load, 5000); return () => clearInterval(t); }, []);

  const connectedCount = devices.filter(d =>
    d.connection_status === 'CONNECTED' || d.connection_status === 'SIMULATED').length;
  const disconnectedCount = devices.filter(d => d.connection_status === 'DISCONNECTED').length;

  const sensors = devices.filter(d => d.device_type === 'Ultrasonic Sensor');
  const mainDevices = devices.filter(d => d.device_type !== 'Ultrasonic Sensor');

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-3">
          <Cpu className="w-5 h-5 text-cyan-400" />
          <h2 className="text-lg font-bold text-white">Device Status</h2>
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 text-sm text-slate-400 hover:text-cyan-400 transition-colors"
        >
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
          Refresh
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3">
        <StatCard label="Total Devices" value={devices.length} icon={<Cpu className="w-4 h-4" />} color="#22d3ee" />
        <StatCard label="Connected" value={connectedCount}
          icon={<Wifi className="w-4 h-4" />} color="#22c55e" />
        <StatCard label="Disconnected" value={disconnectedCount}
          icon={<Wifi className="w-4 h-4" />} color={disconnectedCount > 0 ? '#ef4444' : '#22c55e'} />
        <StatCard label="Mode"
          value={sysInfo?.mode ?? '—'}
          icon={<Cpu className="w-4 h-4" />}
          color={sysInfo?.mode === 'SIMULATION' ? '#22d3ee' : '#22c55e'}
        />
      </div>

      {/* System info */}
      {sysInfo && (
        <Card title="System Information" titleIcon={<Cpu className="w-3.5 h-3.5 text-cyan-400" />}>
          <div className="grid grid-cols-3 gap-4 text-sm">
            <div>
              <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">Operating Mode</div>
              <div className={`font-semibold ${sysInfo.mode === 'SIMULATION' ? 'text-cyan-400' : 'text-green-400'}`}>
                {sysInfo.mode}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">Simulation</div>
              <div className={sysInfo.simulation_running ? 'text-green-400' : 'text-slate-400'}>
                {sysInfo.simulation_running ? `Running — ${sysInfo.simulation_scenario}` : 'Stopped'}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">Hardware</div>
              <div className={sysInfo.hardware_connected ? 'text-green-400' : 'text-slate-400'}>
                {sysInfo.hardware_connected
                  ? `Connected (${formatTimeAgo(sysInfo.hardware_last_seen)})`
                  : 'Not connected'}
              </div>
            </div>
            <div>
              <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">Critical Threshold</div>
              <div className="text-red-400 font-mono">{sysInfo.thresholds?.critical_cm} cm</div>
            </div>
            <div>
              <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">Warning Threshold</div>
              <div className="text-orange-400 font-mono">{sysInfo.thresholds?.warning_cm} cm</div>
            </div>
            <div>
              <div className="text-xs text-slate-400 uppercase tracking-wider mb-1">Caution Threshold</div>
              <div className="text-yellow-400 font-mono">{sysInfo.thresholds?.caution_cm} cm</div>
            </div>
          </div>
        </Card>
      )}

      {/* Main devices */}
      <Card title="Hardware Devices" titleIcon={<Cpu className="w-3.5 h-3.5 text-cyan-400" />}>
        {loading && mainDevices.length === 0 ? (
          <div className="flex justify-center py-8"><Spinner size={28} /></div>
        ) : (
          <div className="space-y-3">
            {mainDevices.map(d => (
              <div
                key={d.id}
                className="flex items-center gap-4 p-3 rounded-lg border"
                style={{ borderColor: 'rgba(13, 32, 112, 0.5)', background: 'rgba(2, 8, 24, 0.4)' }}
              >
                <div className="text-cyan-400 flex-shrink-0">
                  {DEVICE_ICONS[d.device_type] ?? <Cpu className="w-5 h-5" />}
                </div>
                <div className="flex-1 min-w-0">
                  <div className="font-medium text-sm text-slate-200">{d.device_name}</div>
                  <div className="text-xs text-slate-500">{d.device_type}</div>
                </div>
                <StatusDot status={d.connection_status} label={d.connection_status} />
                <div className="text-xs text-slate-500 text-right">
                  <div>Last seen</div>
                  <div>{formatTimeAgo(d.last_seen)}</div>
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Sensors grid */}
      <Card title="Ultrasonic Sensors" titleIcon={<Radio className="w-3.5 h-3.5 text-cyan-400" />}>
        {loading && sensors.length === 0 ? (
          <div className="flex justify-center py-8"><Spinner size={28} /></div>
        ) : (
          <div className="grid grid-cols-3 gap-3">
            {sensors.map(d => (
              <div
                key={d.id}
                className="p-3 rounded-lg border flex flex-col gap-2"
                style={{ borderColor: 'rgba(13, 32, 112, 0.5)', background: 'rgba(2, 8, 24, 0.4)' }}
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono font-bold text-cyan-400 text-sm">
                    {d.device_name.replace('fogguard-sensor-', '').toUpperCase()}
                  </span>
                  <StatusDot status={d.connection_status} />
                </div>
                <div className="text-xs text-slate-500">
                  Last: {formatTimeAgo(d.last_seen)}
                </div>
              </div>
            ))}
          </div>
        )}
      </Card>

      {/* Hardware integration note */}
      <div
        className="rounded-xl border p-4 text-sm"
        style={{ borderColor: 'rgba(13, 32, 112, 0.5)', background: 'rgba(6, 15, 46, 0.5)' }}
      >
        <div className="flex items-center gap-2 text-cyan-400 font-semibold mb-2">
          <Bluetooth className="w-4 h-4" />
          Hardware Integration Guide
        </div>
        <div className="text-slate-400 space-y-1">
          <p>To connect real ESP32 hardware, POST sensor data to:</p>
          <code className="block font-mono text-xs bg-black/30 rounded p-2 text-cyan-300 mt-2">
            POST http://&lt;backend-ip&gt;:8000/api/v1/iot/telemetry
          </code>
          <p className="mt-2">See <span className="text-cyan-400">docs/hardware-integration.md</span> for the full payload schema and ESP32 firmware example.</p>
        </div>
      </div>
    </div>
  );
}
