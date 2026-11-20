"""High-Resolution Telemetry Latency & Throughput Tracker.
Calculates real-time P50, P95, P99 latency percentiles, telemetry frame rates (Hz),
and frame sequence continuity without locking the hot path.
"""
import time
import math
from collections import deque
from typing import Dict, Any, Optional, List


class LatencyTracker:
    def __init__(self, window_size: int = 500):
        self._window_size = window_size
        self._samples: deque = deque(maxlen=window_size)
        self._timestamps: deque = deque(maxlen=window_size)
        self._last_seq: Optional[int] = None
        self._dropped_frames: int = 0
        self._total_frames: int = 0
        self._start_time: float = time.time()

    def record(self, proc_ms: float, seq: Optional[int] = None):
        """Record a single telemetry frame processing duration and sequence number."""
        now = time.time()
        self._samples.append(proc_ms)
        self._timestamps.append(now)
        self._total_frames += 1

        if seq is not None and self._last_seq is not None:
            # Check for dropped frames
            diff = seq - self._last_seq
            if diff > 1:
                self._dropped_frames += (diff - 1)
        if seq is not None:
            self._last_seq = seq

    def reset(self):
        """Reset all tracked metrics."""
        self._samples.clear()
        self._timestamps.clear()
        self._last_seq = None
        self._dropped_frames = 0
        self._total_frames = 0
        self._start_time = time.time()

    def get_stats(self) -> Dict[str, Any]:
        """Compute percentile latencies and frame rates across the rolling window."""
        if not self._samples:
            return {
                "total_frames": self._total_frames,
                "window_samples": 0,
                "fps": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
                "avg_ms": 0.0,
                "min_ms": 0.0,
                "max_ms": 0.0,
                "dropped_frames": self._dropped_frames,
                "last_seq": self._last_seq,
            }

        sorted_samples: List[float] = sorted(self._samples)
        n = len(sorted_samples)

        def percentile(p: float) -> float:
            k = (n - 1) * (p / 100.0)
            f = math.floor(k)
            c = math.ceil(k)
            if f == c:
                return sorted_samples[int(k)]
            d0 = sorted_samples[int(f)] * (c - k)
            d1 = sorted_samples[int(c)] * (k - f)
            return round(d0 + d1, 3)

        # FPS calculation over the window
        fps = 0.0
        if len(self._timestamps) >= 2:
            elapsed = self._timestamps[-1] - self._timestamps[0]
            if elapsed > 0:
                fps = round((len(self._timestamps) - 1) / elapsed, 2)

        return {
            "total_frames": self._total_frames,
            "window_samples": n,
            "fps": fps,
            "p50_ms": percentile(50.0),
            "p95_ms": percentile(95.0),
            "p99_ms": percentile(99.0),
            "avg_ms": round(sum(sorted_samples) / n, 3),
            "min_ms": round(sorted_samples[0], 3),
            "max_ms": round(sorted_samples[-1], 3),
            "dropped_frames": self._dropped_frames,
            "last_seq": self._last_seq,
        }


# Global singleton instance
latency_tracker = LatencyTracker(window_size=500)
