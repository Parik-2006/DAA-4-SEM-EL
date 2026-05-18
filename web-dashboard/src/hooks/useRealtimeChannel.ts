import { useEffect, useRef, useState } from "react";

export type EventEnvelope = {
  event: string;
  section_id?: string;
  payload?: any;
  ts?: string;
};

type Opts = {
  clientId: string;
  role?: string;
  token?: string;
  urlBase?: string; // e.g. '' or 'http://localhost:8000'
  onEvent?: (env: EventEnvelope) => void;
  pollingInterval?: number;
  maxReconnects?: number;
};

export default function useRealtimeChannel(opts: Opts) {
  const { clientId, role = "viewer", token, urlBase = (import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000'), onEvent, pollingInterval = 15000, maxReconnects = 5 } = opts;
  const wsRef = useRef<WebSocket | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const pollRef = useRef<number | null>(null);
  const [connected, setConnected] = useState(false);
  const [protocol, setProtocol] = useState<string | null>(null);
  const [reconnects, setReconnects] = useState(0);
  const [lastError, setLastError] = useState<string | null>(null);

  const makeQuery = (extra?: Record<string, string>) => {
    const qp: Record<string, string> = { client_id: clientId, role };
    if (token) qp.token = token;
    if (extra) Object.assign(qp, extra);
    return Object.entries(qp).map(([k, v]) => `${encodeURIComponent(k)}=${encodeURIComponent(v)}`).join("&");
  };

  useEffect(() => {
    let mounted = true;

    const tryWebsocket = () => {
      try {
        const url = (urlBase || "") + `/api/v1/realtime/ws?${makeQuery()}`.replace(/^http:/, "ws:").replace(/^https:/, "wss:");
        const ws = new WebSocket(url);
        wsRef.current = ws;
        setProtocol("ws");

        ws.onopen = () => {
          if (!mounted) return;
          setConnected(true);
          setLastError(null);
          setReconnects(0);
        };
        ws.onmessage = (ev) => {
          try {
            const data = JSON.parse(ev.data);
            onEvent?.(data as EventEnvelope);
          } catch (e) {
            // ignore
          }
        };
        ws.onclose = () => {
          if (!mounted) return;
          setConnected(false);
          setProtocol(null);
          setReconnects((r) => r + 1);
        };
        ws.onerror = (err) => {
          setLastError(String(err));
        };
      } catch (err) {
        setLastError(String(err));
      }
    };

    const trySSE = () => {
      try {
        const url = (urlBase || "") + `/api/v1/realtime/sse?${makeQuery()}`;
        const es = new EventSource(url);
        esRef.current = es;
        setProtocol("sse");
        es.onopen = () => {
          if (!mounted) return;
          setConnected(true);
          setLastError(null);
          setReconnects(0);
        };
        es.onmessage = (ev) => {
          try {
            const data = JSON.parse(ev.data);
            onEvent?.(data as EventEnvelope);
          } catch (e) {}
        };
        es.onerror = () => {
          if (!mounted) return;
          setConnected(false);
          setProtocol(null);
          setReconnects((r) => r + 1);
        };
      } catch (err) {
        setLastError(String(err));
      }
    };

    const startPolling = () => {
      setProtocol("poll");
      const id = window.setInterval(async () => {
        try {
          const res = await fetch((urlBase || "") + `/api/v1/realtime/poll?${makeQuery()}`);
          if (res.ok) {
            const data = await res.json();
            if (Array.isArray(data)) data.forEach((d) => onEvent?.(d));
            setConnected(true);
          }
        } catch (err) {
          setLastError(String(err));
        }
      }, pollingInterval);
      pollRef.current = id;
    };

    // try websocket then sse then polling
    tryWebsocket();

    const watcher = setInterval(() => {
      // if ws failed and reconnects increased, fall back
      if (wsRef.current == null && esRef.current == null && protocol == null) {
        if (reconnects >= maxReconnects) {
          trySSE();
        } else {
          tryWebsocket();
        }
      }

      if (protocol == null && reconnects >= maxReconnects && esRef.current == null && pollRef.current == null) {
        trySSE();
      }

      if (protocol == null && reconnects >= maxReconnects && esRef.current == null && pollRef.current == null) {
        startPolling();
      }
    }, 3000);

    return () => {
      mounted = false;
      clearInterval(watcher);
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [clientId, role, token]);

  const disconnect = () => {
    if (wsRef.current) wsRef.current.close();
    if (esRef.current) esRef.current.close();
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; }
    setConnected(false);
    setProtocol(null);
  };

  return { connected, protocol, reconnects, lastError, disconnect };
}
