// Settings Page
import { useEffect, useState } from 'react';
import { Settings as SettingsIcon, Save, RotateCcw } from 'lucide-react';
import { Card, Button } from '../components/ui';
import { useStore } from '../store/useStore';
import * as api from '../services/api';
import type { ThresholdConfig } from '../types';

export function Settings() {
  const { thresholds, setThresholds } = useStore();
  const [local, setLocal] = useState<ThresholdConfig>(thresholds);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getThresholds().then(t => {
      setLocal(t);
      setThresholds(t);
    }).catch(() => {});
  }, []);

  const handleSave = async () => {
    setLoading(true);
    try {
      await api.updateThresholds(local);
      setThresholds(local);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch { /* silent */ }
    setLoading(false);
  };

  const handleReset = () => {
    const defaults: ThresholdConfig = { critical_cm: 50, warning_cm: 100, caution_cm: 150, max_range_cm: 400 };
    setLocal(defaults);
  };

  const ThresholdRow = ({
    label, field, color, description
  }: { label: string; field: keyof ThresholdConfig; color: string; description: string }) => (
    <div className="flex items-center gap-6 py-3 border-b" style={{ borderColor: 'rgba(13, 32, 112, 0.3)' }}>
      <div className="flex-1">
        <div className="text-sm font-medium text-slate-200">{label}</div>
        <div className="text-xs text-slate-500">{description}</div>
      </div>
      <div className="flex items-center gap-3">
        <input
          type="range"
          min={10}
          max={field === 'max_range_cm' ? 600 : 300}
          step={5}
          value={local[field]}
          onChange={e => setLocal(prev => ({ ...prev, [field]: Number(e.target.value) }))}
          className="w-32 accent-cyan-400"
        />
        <div
          className="font-mono text-sm font-semibold w-20 text-right"
          style={{ color }}
        >
          {local[field]} cm
        </div>
      </div>
    </div>
  );

  return (
    <div className="h-full overflow-y-auto p-4 space-y-4">
      <div className="flex items-center gap-3">
        <SettingsIcon className="w-5 h-5 text-cyan-400" />
        <h2 className="text-lg font-bold text-white">Settings</h2>
      </div>

      {/* Threshold config */}
      <Card
        title="Detection Thresholds"
        titleIcon={<SettingsIcon className="w-3.5 h-3.5 text-cyan-400" />}
        headerRight={
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={handleReset}>
              <RotateCcw className="w-3.5 h-3.5" />
              Reset
            </Button>
            <Button variant="primary" size="sm" onClick={handleSave} disabled={loading}>
              <Save className="w-3.5 h-3.5" />
              {saved ? 'Saved!' : 'Save'}
            </Button>
          </div>
        }
      >
        <div className="space-y-0">
          <ThresholdRow
            label="Critical Threshold"
            field="critical_cm"
            color="#ef4444"
            description="Below this distance: CRITICAL alert"
          />
          <ThresholdRow
            label="Warning Threshold"
            field="warning_cm"
            color="#f97316"
            description="Below this distance: WARNING alert"
          />
          <ThresholdRow
            label="Caution Threshold"
            field="caution_cm"
            color="#eab308"
            description="Below this distance: CAUTION alert"
          />
          <ThresholdRow
            label="Max Sensor Range"
            field="max_range_cm"
            color="#22d3ee"
            description="Above this distance: sensor treated as CLEAR"
          />
        </div>

        {/* Preview */}
        <div className="mt-4 grid grid-cols-4 gap-3">
          <div className="rounded-lg p-3 text-center border" style={{ borderColor: '#ef444430', background: '#ef444410' }}>
            <div className="text-xs text-red-400 uppercase tracking-wider">Critical</div>
            <div className="text-sm font-mono font-bold text-red-400">0–{local.critical_cm} cm</div>
          </div>
          <div className="rounded-lg p-3 text-center border" style={{ borderColor: '#f9731630', background: '#f9731610' }}>
            <div className="text-xs text-orange-400 uppercase tracking-wider">Warning</div>
            <div className="text-sm font-mono font-bold text-orange-400">{local.critical_cm}–{local.warning_cm} cm</div>
          </div>
          <div className="rounded-lg p-3 text-center border" style={{ borderColor: '#eab30830', background: '#eab30810' }}>
            <div className="text-xs text-yellow-400 uppercase tracking-wider">Caution</div>
            <div className="text-sm font-mono font-bold text-yellow-400">{local.warning_cm}–{local.caution_cm} cm</div>
          </div>
          <div className="rounded-lg p-3 text-center border" style={{ borderColor: '#22c55e30', background: '#22c55e10' }}>
            <div className="text-xs text-green-400 uppercase tracking-wider">Safe</div>
            <div className="text-sm font-mono font-bold text-green-400">{local.caution_cm}+ cm</div>
          </div>
        </div>
      </Card>

      {/* System info */}
      <Card title="System" titleIcon={<SettingsIcon className="w-3.5 h-3.5 text-cyan-400" />}>
        <div className="space-y-3 text-sm">
          <div className="flex justify-between py-2 border-b" style={{ borderColor: 'rgba(13, 32, 112, 0.3)' }}>
            <span className="text-slate-400">Backend URL</span>
            <span className="font-mono text-cyan-400">http://localhost:8000</span>
          </div>
          <div className="flex justify-between py-2 border-b" style={{ borderColor: 'rgba(13, 32, 112, 0.3)' }}>
            <span className="text-slate-400">WebSocket</span>
            <span className="font-mono text-cyan-400">ws://localhost:8000/ws</span>
          </div>
          <div className="flex justify-between py-2 border-b" style={{ borderColor: 'rgba(13, 32, 112, 0.3)' }}>
            <span className="text-slate-400">API Docs</span>
            <a href="http://localhost:8000/docs" target="_blank" rel="noopener noreferrer"
              className="text-cyan-400 hover:underline font-mono">
              http://localhost:8000/docs
            </a>
          </div>
          <div className="flex justify-between py-2">
            <span className="text-slate-400">Version</span>
            <span className="text-slate-300 font-mono">1.0.0</span>
          </div>
        </div>
      </Card>

      {/* About */}
      <Card title="About FogGuard" titleIcon={<SettingsIcon className="w-3.5 h-3.5 text-cyan-400" />}>
        <div className="text-sm text-slate-400 space-y-2">
          <p><strong className="text-slate-200">FogGuard</strong> is an IoT-based fog-resistant obstacle detection and smart traffic management system.</p>
          <p>Built with React, FastAPI, SQLite, Three.js, and WebSockets for real-time monitoring.</p>
          <div className="mt-3 grid grid-cols-2 gap-2 text-xs">
            <div className="rounded p-2" style={{ background: 'rgba(2, 8, 24, 0.5)', border: '1px solid rgba(13, 32, 112, 0.5)' }}>
              <div className="text-cyan-400 font-semibold mb-1">Hardware</div>
              <div>Arduino + ESP32</div>
              <div>6× Ultrasonic Sensors</div>
              <div>3× Traffic LEDs</div>
            </div>
            <div className="rounded p-2" style={{ background: 'rgba(2, 8, 24, 0.5)', border: '1px solid rgba(13, 32, 112, 0.5)' }}>
              <div className="text-cyan-400 font-semibold mb-1">Software</div>
              <div>React + Three.js</div>
              <div>FastAPI + SQLite</div>
              <div>WebSocket real-time</div>
            </div>
          </div>
        </div>
      </Card>
    </div>
  );
}
