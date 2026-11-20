// Utility functions
import type { WarningLevel, ThresholdConfig } from '../types';

export function classifyDistance(
  distance: number | null,
  thresholds: ThresholdConfig = { critical_cm: 50, warning_cm: 100, caution_cm: 150, max_range_cm: 400 }
): WarningLevel {
  if (distance === null || distance <= 0 || distance > thresholds.max_range_cm) return 'CLEAR';
  if (distance <= thresholds.critical_cm) return 'CRITICAL';
  if (distance <= thresholds.warning_cm) return 'WARNING';
  if (distance <= thresholds.caution_cm) return 'CAUTION';
  return 'SAFE';
}

export function warningLevelColor(level: WarningLevel): string {
  switch (level) {
    case 'CRITICAL': return '#ef4444';
    case 'WARNING': return '#f97316';
    case 'CAUTION': return '#eab308';
    case 'SAFE': return '#22c55e';
    default: return '#94a3b8'; // CLEAR / unknown
  }
}

export function warningLevelBg(level: WarningLevel): string {
  switch (level) {
    case 'CRITICAL': return 'bg-red-500/20 border-red-500/50 text-red-400';
    case 'WARNING': return 'bg-orange-500/20 border-orange-500/50 text-orange-400';
    case 'CAUTION': return 'bg-yellow-500/20 border-yellow-500/50 text-yellow-400';
    case 'SAFE': return 'bg-green-500/20 border-green-500/50 text-green-400';
    default: return 'bg-slate-500/20 border-slate-500/50 text-slate-400';
  }
}

export function trafficStateColor(state: string): string {
  switch (state) {
    case 'RED': return '#ef4444';
    case 'YELLOW': return '#eab308';
    case 'GREEN': return '#22c55e';
    default: return '#94a3b8';
  }
}

export function formatDistance(d: number | null): string {
  if (d === null || d === undefined) return 'CLEAR';
  return `${Math.round(d)} cm`;
}

export function formatTimestamp(ts: string | null): string {
  if (!ts) return '—';
  try {
    return new Date(ts).toLocaleString();
  } catch {
    return ts;
  }
}

export function formatTimeAgo(ts: string | null): string {
  if (!ts) return 'Never';
  const diff = (Date.now() - new Date(ts).getTime()) / 1000;
  if (diff < 5) return 'Just now';
  if (diff < 60) return `${Math.round(diff)}s ago`;
  if (diff < 3600) return `${Math.round(diff / 60)}m ago`;
  return `${Math.round(diff / 3600)}h ago`;
}

export function cn(...classes: (string | boolean | undefined | null)[]): string {
  return classes.filter(Boolean).join(' ');
}
