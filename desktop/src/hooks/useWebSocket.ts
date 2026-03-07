import { useEffect, useRef, useCallback } from "react";
import { useAgentStore, useSettingsStore } from "@/store/agentStore";
import type { WsEvent } from "@/types";

const RECONNECT_DELAY = 3000;  // start at 3s
const MAX_RECONNECT   = 10;    // give up after ~10 tries (~5 min total with backoff)

/**
 * useWebSocket — connects to the Python backend when it's running.
 *
 * KEY BEHAVIORS:
 * - Completely silent when backend isn't running. No console errors, no crash.
 * - Exponential backoff on disconnect (3s → 4.5s → 6.75s … capped at 30s).
 * - Gives up after MAX_RECONNECT attempts so it stops looping forever.
 * - User can manually retry by restarting the agent from the UI.
 * - Safe to mount when backend is offline — the app still renders fine.
 */
export function useWebSocket() {
  const wsRef            = useRef<WebSocket | null>(null);
  const reconnectCount   = useRef(0);
  const reconnectTimer   = useRef<ReturnType<typeof setTimeout> | null>(null);
  const intentionalClose = useRef(false);
  const mounted          = useRef(true);

  const { setConnected, setConnecting, addMessage, setAgentState } = useAgentStore();
  const { settings } = useSettingsStore();

  const handleEvent = useCallback((event: WsEvent) => {
    if (event.type === "transcript") {
      addMessage({
        role:    event.role === "user" ? "user" : "assistant",
        text:    event.text,
        actions: undefined,
      });
    } else if (event.type === "status") {
      setAgentState(event.state);
    }
  }, [addMessage, setAgentState]);

  const connect = useCallback(() => {
    if (!mounted.current) return;
    if (wsRef.current?.readyState === WebSocket.OPEN) return;
    if (wsRef.current?.readyState === WebSocket.CONNECTING) return;

    setConnecting(true);

    const url = `ws://127.0.0.1:${settings.apiPort}/ws/events`;

    let ws: WebSocket;
    try {
      ws = new WebSocket(url);
    } catch {
      // WebSocket constructor itself can throw if URL is malformed
      setConnecting(false);
      setAgentState("disconnected");
      return;
    }

    wsRef.current = ws;

    ws.onopen = () => {
      if (!mounted.current) { ws.close(); return; }
      reconnectCount.current = 0;
      setConnected(true);
      setConnecting(false);
      setAgentState("idle");
      addMessage({ role: "system", text: "✓ Connected to Samantha" });
    };

    ws.onmessage = (evt) => {
      try {
        const event: WsEvent = JSON.parse(evt.data as string);
        handleEvent(event);
      } catch { /* ignore malformed events */ }
    };

    // onerror fires before onclose — just clear state, let onclose handle retry
    ws.onerror = () => {
      setConnected(false);
      setConnecting(false);
      // Don't log — this fires every time the backend isn't running, which is normal
    };

    ws.onclose = () => {
      if (!mounted.current) return;
      setConnected(false);
      setConnecting(false);
      setAgentState("disconnected");

      if (intentionalClose.current) return;
      if (reconnectCount.current >= MAX_RECONNECT) return; // gave up silently

      reconnectCount.current++;
      const delay = Math.min(RECONNECT_DELAY * Math.pow(1.5, reconnectCount.current - 1), 30_000);
      reconnectTimer.current = setTimeout(connect, delay);
    };
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings.apiPort]);

  // Auto-connect on mount (safely — will just silently fail if backend is offline)
  useEffect(() => {
    mounted.current        = true;
    intentionalClose.current = false;
    connect();

    return () => {
      mounted.current          = false;
      intentionalClose.current = true;
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      wsRef.current?.close();
    };
  }, [connect]);

  // Reset + reconnect when apiPort changes
  useEffect(() => {
    intentionalClose.current = false;
    reconnectCount.current   = 0;
    wsRef.current?.close();
    connect();
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings.apiPort]);

  const manualReconnect = useCallback(() => {
    intentionalClose.current = false;
    reconnectCount.current   = 0;
    wsRef.current?.close();
    connect();
  }, [connect]);

  return { manualReconnect };
}
