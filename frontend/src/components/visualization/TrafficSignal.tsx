
import { useEffect, useState } from 'react';
import type { TrafficSignalStatus } from '../../types';
import { trafficStateColor } from '../../utils';

interface TrafficSignalProps {
  signal: TrafficSignalStatus | null;
  size?: 'sm' | 'md' | 'lg';
}

export function TrafficSignal({ signal, size = 'md' }: TrafficSignalProps) {
  const state = signal?.state ?? 'UNKNOWN';

  const [countdown, setCountdown] = useState<number | null>(null);

  useEffect(() => {
    if (!signal?.duration_seconds) {
      setCountdown(null);
      return;
    }

    setCountdown(signal.duration_seconds);

    const timer = setInterval(() => {
      setCountdown(prev => {
        if (prev === null || prev <= 1) {
          clearInterval(timer);
          return null;
        }
        return prev - 1;
      });
    }, 1000);

    return () => clearInterval(timer);
  }, [signal?.state, signal?.duration_seconds]);

  const sizes = {
    sm: { housing: 'w-9', light: 'w-5 h-5', gap: 'gap-1' },
    md: { housing: 'w-20', light: 'w-12 h-12', gap: 'gap-3' },
    lg: { housing: 'w-28', light: 'w-16 h-16', gap: 'gap-4' },
  };

  const s = sizes[size];

  const lights = [
    { color: 'RED', active: state === 'RED', bg: '#ef4444', inactive: '#351a20' },
    { color: 'YELLOW', active: state === 'YELLOW', bg: '#eab308', inactive: '#352e19' },
    { color: 'GREEN', active: state === 'GREEN', bg: '#22c55e', inactive: '#173322' },
  ];

  return (
    <div className="flex flex-col items-center gap-1">
      <div
        className={`${s.housing} rounded-2xl p-1.5 flex flex-col items-center ${s.gap}`}
        style={{
          background: '#111b31',
          border: '1px solid #334155'
        }}
      >
        {lights.map(({ color, active, bg, inactive }) => (
          <div
            key={color}
            className={`${s.light} rounded-full transition-colors duration-300`}
            style={{
              backgroundColor: active ? bg : inactive,
              boxShadow: active ? `0 0 18px 3px ${bg}55` : 'none'
            }}
          />
        ))}
      </div>

      <div
        className="text-xs font-semibold leading-4 tracking-wide"
        style={{ color: trafficStateColor(state) }}
      >
        {state}
      </div>

      {countdown !== null && (
        <div className="whitespace-nowrap text-[10px] leading-3 text-slate-400 font-mono">
          {countdown}s remaining
        </div>
      )}
    </div>
  );
}
