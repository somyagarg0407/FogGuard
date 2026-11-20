// Simulation Control Panel
import { useEffect, useState } from 'react';
import { Play, Square, RotateCcw, FlaskConical, ChevronDown } from 'lucide-react';
import { useStore } from '../../store/useStore';
import { Button } from '../../components/ui';
import * as api from '../../services/api';
import type { SimulationScenario } from '../../types';

export function SimulationControl() {
  const { simulationRunning, simulationScenario, setSimulationRunning, setSimulationScenario } = useStore();
  const [scenarios, setScenarios] = useState<SimulationScenario[]>([]);
  const [speed, setSpeed] = useState(1.0);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    api.getSimulationScenarios().then(r => setScenarios(r.scenarios)).catch(() => {});
    api.getSimulationStatus().then(r => {
      setSimulationRunning(r.running);
      setSimulationScenario(r.scenario);
    }).catch(() => {});
  }, []);

  const handleStart = async () => {
    setLoading(true);
    try {
      await api.controlSimulation('start', simulationScenario, speed);
      setSimulationRunning(true);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const handleStop = async () => {
    setLoading(true);
    try {
      await api.controlSimulation('stop');
      setSimulationRunning(false);
    } catch (e) { console.error(e); }
    setLoading(false);
  };

  const handleReset = async () => {
    try { await api.controlSimulation('reset'); } catch { /* silent */ }
  };

  return (
    <div
      className="dashboard-simulation rounded-xl border p-3 flex items-center gap-4 flex-wrap"
      style={{ background: 'rgba(6, 15, 46, 0.7)', borderColor: 'rgba(13, 32, 112, 0.5)' }}
    >
      <div className="flex items-center gap-2 text-sm font-semibold text-cyan-400">
        <FlaskConical className="w-4 h-4" />
        SIMULATION
        {simulationRunning && (
          <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
        )}
      </div>

      {/* Scenario selector */}
      <div className="relative">
        <select
          value={simulationScenario}
          onChange={e => setSimulationScenario(e.target.value)}
          disabled={simulationRunning || loading}
          className="appearance-none pl-3 pr-8 py-1.5 text-sm rounded-lg border bg-transparent text-slate-200 cursor-pointer disabled:opacity-50"
          style={{ borderColor: 'rgba(13, 32, 112, 0.8)', background: 'rgba(2, 8, 24, 0.5)' }}
        >
          {scenarios.map(s => (
            <option key={s.id} value={s.id} style={{ background: '#060f2e' }}>
              {s.name}
            </option>
          ))}
        </select>
        <ChevronDown className="w-3.5 h-3.5 absolute right-2 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
      </div>

      {/* Speed */}
      <div className="flex items-center gap-2 text-sm text-slate-400">
        <span>Speed:</span>
        <input
          type="range"
          min={0.5}
          max={5}
          step={0.5}
          value={speed}
          onChange={e => setSpeed(Number(e.target.value))}
          disabled={simulationRunning || loading}
          className="w-24 accent-cyan-400"
        />
        <span className="font-mono text-cyan-400 w-8">{speed}x</span>
      </div>

      <div className="flex items-center gap-2 ml-auto">
        {!simulationRunning ? (
          <Button onClick={handleStart} disabled={loading} variant="primary" size="sm">
            <Play className="w-3.5 h-3.5" />
            Start
          </Button>
        ) : (
          <Button onClick={handleStop} disabled={loading} variant="danger" size="sm">
            <Square className="w-3.5 h-3.5" />
            Stop
          </Button>
        )}
        <Button onClick={handleReset} disabled={loading} variant="ghost" size="sm">
          <RotateCcw className="w-3.5 h-3.5" />
          Reset
        </Button>
      </div>
    </div>
  );
}
