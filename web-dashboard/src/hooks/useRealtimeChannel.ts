import { useEffect, useMemo, useRef, useState } from "react";

export type EventEnvelope = {
  event: string;
  section_id?: string;
  payload?: any;
  ts?: string;
};

type RealtimeProtocol = "ws" | "sse";

type Opts = {
  clientId: string;
  sectionId: string;
  role?: string;
  token?: string;
  urlBase?: string;
  onEvent?: (env: EventEnvelope) => void;
  maxReconnects?: number;
};

const SSE_EVENT_NAMES = [
  "connected",
  "pong",
  "attendance_marked",
  "bulk_attendance",
  "attendance_updated",
  "window_tick",
] as const;

function clampDelay(attempt: number): number {
  return Math.min(1_000 * Math.pow(1.6, attempt), 15_000);
}

function normalizeBase(urlBase: string): string {
  return (urlBase || "").replace(/\/$/, "");
}

function websocketBase(urlBase: string): string {
  return normalizeBase(urlBase).replace(/^http:/, "ws:").replace(/^https:/, "wss:");
}

export default function useRealtimeChannel(opts: Opts) {
  const {
    clientId,
    sectionId,
    role = "viewer",
    token,
    urlBase = (import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000"),
    onEvent,
    maxReconnects = 3,
  } = opts;

  const wsRef = useRef<WebSocket | null>(null);
  const esRef = useRef<EventSource | null>(null);
  const reconnectTimerRef = useRef<number | null>(null);
  const pingTimerRef = useRef<number | null>(null);
  const wsAttemptsRef = useRef(0);
  const sseAttemptsRef = useRef(0);
  const stoppedRef = useRef(false);
  const onEventRef = useRef(onEvent);

  const [connected, setConnected] = useState(false);
  const [protocol, setProtocol] = useState<RealtimeProtocol | null>(null);
  const [reconnects, setReconnects] = useState(0);
  const [lastError, setLastError] = useState<string | null>(null);

  useEffect(() => {
    onEventRef.current = onEvent;
  }, [onEvent]);

  const query = useMemo(() => {
    const qp: Record<string, string> = { client_id: clientId, role };
    if (token) qp.token = token;
    return new URLSearchParams(qp).toString();
  }, [clientId, role, token]);

  useEffect(() => {
    if (!clientId || !sectionId || !token) {
      setConnected(false);
      setProtocol(null);
      setLastError(!token ? "Realtime token missing" : null);
      return;
    }

    stoppedRef.current = false;
    wsAttemptsRef.current = 0;
    sseAttemptsRef.current = 0;

    const clearTimers = () => {
      if (reconnectTimerRef.current != null) {
        window.clearTimeout(reconnectTimerRef.current);
        reconnectTimerRef.current = null;
      }
      if (pingTimerRef.current != null) {
        window.clearInterval(pingTimerRef.current);
        pingTimerRef.current = null;
      }
    };

    const closeActive = () => {
      if (wsRef.current) {
        wsRef.current.onclose = null;
        wsRef.current.onerror = null;
        wsRef.current.close();
        wsRef.current = null;
      }
      if (esRef.current) {
        esRef.current.close();
        esRef.current = null;
      }
      clearTimers();
    };

    const emit = (raw: string) => {
      try {
        onEventRef.current?.(JSON.parse(raw) as EventEnvelope);
      } catch {
        // Ignore malformed keepalive/proxy frames.
      }
    };

    const schedule = (next: () => void, attempt: number) => {
      if (stoppedRef.current) return;
      const delay = clampDelay(attempt);
      setReconnects((count) => count + 1);
      reconnectTimerRef.current = window.setTimeout(next, delay);
    };

    const connectSSE = () => {
      if (stoppedRef.current) return;
      closeActive();

      const url = `${normalizeBase(urlBase)}/api/v1/realtime/sse/${encodeURIComponent(sectionId)}?${query}`;
      const es = new EventSource(url);
      esRef.current = es;
      setProtocol("sse");

      es.onopen = () => {
        if (stoppedRef.current) return;
        sseAttemptsRef.current = 0;
        setConnected(true);
        setLastError(null);
      };

      es.onmessage = (event) => emit(event.data);
      SSE_EVENT_NAMES.forEach((name) => {
        es.addEventListener(name, (event) => emit((event as MessageEvent).data));
      });

      es.onerror = () => {
        if (stoppedRef.current) return;
        es.close();
        esRef.current = null;
        setConnected(false);
        setProtocol(null);
        setLastError("SSE connection lost");
        schedule(connectSSE, sseAttemptsRef.current++);
      };
    };

    const connectWebSocket = () => {
      if (stoppedRef.current) return;
      closeActive();

      const url = `${websocketBase(urlBase)}/api/v1/realtime/ws/${encodeURIComponent(sectionId)}?${query}`;
      const ws = new WebSocket(url);
      wsRef.current = ws;
      setProtocol("ws");

      ws.onopen = () => {
        if (stoppedRef.current) return;
        wsAttemptsRef.current = 0;
        setConnected(true);
        setLastError(null);
        pingTimerRef.current = window.setInterval(() => {
          if (ws.readyState === WebSocket.OPEN) ws.send("ping");
        }, 20_000);
      };

      ws.onmessage = (event) => emit(event.data);

      ws.onclose = (event) => {
        if (stoppedRef.current) return;
        wsRef.current = null;
        clearTimers();
        setConnected(false);
        setProtocol(null);

        const shouldFallback = wsAttemptsRef.current >= maxReconnects || [4001, 4003].includes(event.code);
        if (shouldFallback) {
          setLastError(`WebSocket unavailable (${event.code || "closed"}); using SSE fallback`);
          connectSSE();
          return;
        }

        setLastError(`WebSocket closed (${event.code || "network"})`);
        schedule(connectWebSocket, wsAttemptsRef.current++);
      };

      ws.onerror = () => {
        setLastError("WebSocket connection error");
      };
    };

    connectWebSocket();

    return () => {
      stoppedRef.current = true;
      closeActive();
      setConnected(false);
      setProtocol(null);
    };
  }, [clientId, sectionId, token, role, query, urlBase, maxReconnects]);

  const disconnect = () => {
    stoppedRef.current = true;
    if (reconnectTimerRef.current != null) window.clearTimeout(reconnectTimerRef.current);
    if (pingTimerRef.current != null) window.clearInterval(pingTimerRef.current);
    if (wsRef.current) wsRef.current.close();
    if (esRef.current) esRef.current.close();
    wsRef.current = null;
    esRef.current = null;
    setConnected(false);
    setProtocol(null);
  };

  return { connected, protocol, reconnects, lastError, disconnect };
}
