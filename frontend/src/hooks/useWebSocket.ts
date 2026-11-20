// WebSocket hook — connects to backend WS and updates store
import { useEffect, useRef } from 'react';
import { useStore } from '../store/useStore';

const WS_URL = `ws://${window.location.hostname}:8000/ws`;

export function useWebSocket() {
  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<number | null>(null);
  const { setWsConnected, updateFromTelemetry, muted } = useStore();
  const moundedRef = useRef(true);

  const connect = () => {
    if (!moundedRef.current) return;
    try {
      const ws = new WebSocket(WS_URL);
      wsRef.current = ws;

      ws.onopen = () => {
        setWsConnected(true);
        if (reconnectTimer.current) {
          clearTimeout(reconnectTimer.current);
          reconnectTimer.current = null;
        }
      };

      ws.onmessage = (event) => {
        try {
          const rxTime = performance.now();
          const msg = JSON.parse(event.data);
          if (msg.type === 'ping') return;
          updateFromTelemetry(msg, rxTime);

          // Audio alert for critical warnings
          if (!muted && msg.new_warnings?.some((w: any) => w.warning_level === 'CRITICAL')) {
            playBeep();
          }
        } catch (e) {
          // Ignore parse errors
        }
      };

      ws.onclose = () => {
        setWsConnected(false);
        wsRef.current = null;
        if (moundedRef.current) {
          reconnectTimer.current = setTimeout(connect, 3000) as unknown as number;
        }
      };

      ws.onerror = () => {
        ws.close();
      };
    } catch (e) {
      setWsConnected(false);
      reconnectTimer.current = setTimeout(connect, 3000) as unknown as number;
    }
  };

  useEffect(() => {
    moundedRef.current = true;
    connect();
    return () => {
      moundedRef.current = false;
      if (wsRef.current) wsRef.current.close();
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
    };
  }, []);

  return wsRef;
}

function playBeep() {
  try {
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.frequency.value = 880;
    gain.gain.setValueAtTime(0.1, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.3);
    osc.start(ctx.currentTime);
    osc.stop(ctx.currentTime + 0.3);
  } catch {
    // Audio not available
  }
}
