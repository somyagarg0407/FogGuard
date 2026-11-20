
import { NavLink } from 'react-router-dom';
import {
  LayoutDashboard, TrafficCone, BarChart3,
  History, Cpu, Settings, Wifi, WifiOff, Activity
} from 'lucide-react';
import { useStore } from '../../store/useStore';
import { cn } from '../../utils';

const NAV_ITEMS = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/traffic', icon: TrafficCone, label: 'Traffic Management' },
  { to: '/analytics', icon: BarChart3, label: 'Analytics' },
  { to: '/history', icon: History, label: 'History' },
  { to: '/devices', icon: Cpu, label: 'Device Status' },
  { to: '/settings', icon: Settings, label: 'Settings' },
];

export function Sidebar() {
  const { wsConnected, simulationRunning, unacknowledgedCount } = useStore();

  return (
    <aside
      className="fog-sidebar h-screen flex-shrink-0 flex flex-col"
      style={{
        width: '250px',
        background: '#080f27',
        borderRight: '1px solid rgba(59,130,246,0.16)'
      }}
    >
      <div className="px-5 py-5 border-b border-white/10">
        <div className="flex items-center gap-3">
          <div className="w-10 h-10 rounded-xl flex items-center justify-center flex-shrink-0"
            style={{ background: 'rgba(96, 165, 250, 0.16)' }}>
            <Activity className="w-5 h-5 text-blue-300" />
          </div>
          <div>
            <h1 className="text-lg font-semibold text-white tracking-tight">FogGuard</h1>
            <p className="text-xs text-slate-400">IoT Dashboard</p>
          </div>
        </div>
      </div>

      <nav className="flex-1 px-3 py-5 overflow-y-auto">
        <div className="space-y-1.5">
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                cn(
                  'flex items-center gap-3 px-3.5 rounded-lg text-sm font-medium transition-all',
                  'min-h-[42px]',
                  isActive
                    ? 'text-cyan-300 bg-cyan-400/15 border border-cyan-400/25'
                    : 'text-slate-400 border border-transparent hover:bg-white/5 hover:text-white'
                )
              }
            >
              <Icon className="w-[18px] h-[18px] flex-shrink-0" />
              <span className="whitespace-nowrap">{label}</span>

              {label === 'History' && unacknowledgedCount > 0 && (
                <span className="ml-auto px-2 py-0.5 text-xs bg-red-500 text-white rounded-full">
                  {unacknowledgedCount}
                </span>
              )}
            </NavLink>
          ))}
        </div>
      </nav>

      <div className="px-5 py-4 border-t border-white/10 space-y-3">
        <div className="flex items-center gap-2 text-sm">
          {wsConnected
            ? <Wifi className="w-4 h-4 text-green-400" />
            : <WifiOff className="w-4 h-4 text-red-400" />
          }
          <span className={wsConnected ? 'text-green-400' : 'text-red-400'}>
            {wsConnected ? 'Live Connected' : 'Disconnected'}
          </span>
        </div>

        {simulationRunning && (
          <div className="flex items-center gap-2 text-sm text-cyan-400">
            <span className="w-2 h-2 rounded-full bg-cyan-400 animate-pulse" />
            Simulation Active
          </div>
        )}
      </div>
    </aside>
  );
}
