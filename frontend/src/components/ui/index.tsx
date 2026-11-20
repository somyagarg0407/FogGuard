import { Check } from 'lucide-react';
import type { ButtonHTMLAttributes, ReactNode } from 'react';
import type { SensorReading, WarningEvent, WarningLevel } from '../../types';
import { ZONE_DISPLAY } from '../../types';
import { cn, formatDistance, formatTimeAgo, warningLevelBg } from '../../utils';

interface CardProps {
  children: ReactNode;
  className?: string;
  title?: string;
  titleIcon?: ReactNode;
  headerRight?: ReactNode;
}

export function Card({ children, className, title, titleIcon, headerRight }: CardProps) {
  return (
    <section className={cn('ui-card', className)}>
      {title && (
        <div className="ui-card-header">
          <div className="ui-card-title">
            {titleIcon}
            <span>{title}</span>
          </div>
          {headerRight}
        </div>
      )}
      <div className="ui-card-body">{children}</div>
    </section>
  );
}

interface BadgeProps {
  children: ReactNode;
  variant?: 'default' | 'critical' | 'warning' | 'caution' | 'safe' | 'info';
  className?: string;
}

const BADGE_STYLES: Record<NonNullable<BadgeProps['variant']>, string> = {
  default: 'bg-slate-500/15 border-slate-500/25 text-slate-300',
  critical: 'bg-red-500/15 border-red-500/25 text-red-400',
  warning: 'bg-orange-500/15 border-orange-500/25 text-orange-400',
  caution: 'bg-yellow-500/15 border-yellow-500/25 text-yellow-400',
  safe: 'bg-green-500/15 border-green-500/25 text-green-400',
  info: 'bg-blue-500/15 border-blue-500/25 text-blue-400',
};

export function Badge({ children, variant = 'default', className }: BadgeProps) {
  return (
    <span className={cn('inline-flex items-center rounded-full border px-2 py-0.5 text-xs font-medium', BADGE_STYLES[variant], className)}>
      {children}
    </span>
  );
}

interface StatCardProps {
  label: string;
  value: string | number;
  icon?: ReactNode;
  color?: string;
  sub?: string;
}

export function StatCard({ label, value, icon, color = '#60a5fa', sub }: StatCardProps) {
  return (
    <section className="stat-card">
      <div className="stat-card-label">
        {icon && <span style={{ color }}>{icon}</span>}
        <span>{label}</span>
      </div>
      <div className="stat-card-value" style={{ color }}>{value}</div>
      {sub && <div className="stat-card-sub">{sub}</div>}
    </section>
  );
}

const STATUS_COLORS: Record<string, string> = {
  CONNECTED: '#22c55e',
  SIMULATED: '#60a5fa',
  DISCONNECTED: '#ef4444',
  UNKNOWN: '#9ca3af',
  ERROR: '#ef4444',
};

export function StatusDot({ status, label }: { status: string; label?: string }) {
  const color = STATUS_COLORS[status] ?? STATUS_COLORS.UNKNOWN;

  return (
    <div className="flex items-center gap-2">
      <span className="h-2 w-2 flex-shrink-0 rounded-full" style={{ backgroundColor: color }} />
      {label && <span className="text-sm" style={{ color }}>{label}</span>}
    </div>
  );
}

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: 'primary' | 'secondary' | 'danger' | 'ghost';
  size?: 'sm' | 'md';
}

const BUTTON_STYLES: Record<NonNullable<ButtonProps['variant']>, string> = {
  primary: 'bg-blue-500 hover:bg-blue-400 text-white border-transparent',
  secondary: 'bg-slate-700 hover:bg-slate-600 text-slate-100 border-slate-600',
  danger: 'bg-red-600 hover:bg-red-500 text-white border-transparent',
  ghost: 'bg-transparent hover:bg-white/5 text-slate-300 border-transparent',
};

export function Button({
  children,
  variant = 'primary',
  size = 'md',
  className,
  type = 'button',
  ...props
}: ButtonProps) {
  return (
    <button
      type={type}
      className={cn(
        'inline-flex items-center justify-center gap-2 rounded-lg border font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-50',
        BUTTON_STYLES[variant],
        size === 'sm' ? 'px-3 py-1.5 text-xs' : 'px-4 py-2 text-sm',
        className,
      )}
      {...props}
    >
      {children}
    </button>
  );
}

export function Spinner({ size = 16 }: { size?: number }) {
  return (
    <div
      className="animate-spin rounded-full border-2 border-blue-400/25 border-t-blue-400"
      style={{ width: size, height: size }}
      role="status"
      aria-label="Loading"
    />
  );
}

const SENSOR_ROW_CLASSES: Record<WarningLevel, string> = {
  CRITICAL: 'sensor-row-critical',
  WARNING: 'sensor-row-warning',
  CAUTION: 'sensor-row-caution',
  SAFE: 'sensor-row-safe',
  CLEAR: 'sensor-row-clear',
};

export function SensorRow({ sensor }: { sensor: SensorReading }) {
  const zoneName = ZONE_DISPLAY[sensor.zone] ?? sensor.zone;

  return (
    <div className={cn('sensor-row', SENSOR_ROW_CLASSES[sensor.warning_level])}>
      <span className="sensor-row-name">{zoneName}</span>
      <span className="sensor-row-distance">{formatDistance(sensor.distance_cm)}</span>
    </div>
  );
}

interface WarningCardProps {
  warning: WarningEvent;
  onAck?: (id: number) => void;
}

export function WarningCard({ warning, onAck }: WarningCardProps) {
  return (
    <div className={cn(
      'flex items-start gap-3 rounded-lg border p-2.5',
      warningLevelBg(warning.warning_level),
      warning.acknowledged && 'opacity-50',
    )}>
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium leading-snug">{warning.warning_message}</p>
        <p className="mt-1 text-xs text-slate-400">{formatTimeAgo(warning.timestamp)}</p>
      </div>
      {!warning.acknowledged && onAck && (
        <button
          type="button"
          onClick={() => onAck(warning.id)}
          className="flex-shrink-0 rounded p-1 transition-colors hover:bg-white/10"
          title="Acknowledge"
          aria-label="Acknowledge warning"
        >
          <Check className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}
