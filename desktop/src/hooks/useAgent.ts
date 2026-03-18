import { useCallback, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useAgentStore, useSettingsStore } from "@/store/agentStore";
import type { HistoryResponse } from "@/types";

export function useAgent() {
  const { setBackendRunning, setHistory, addMessage, backendRunning } = useAgentStore();
  const { settings } = useSettingsStore();

  // ── Check if backend is already running ───────────────────────────────────
  const checkBackendHealth = useCallback(async () => {
    try {
      const res = await fetch(
        `http://127.0.0.1:${settings.apiPort}/health`,
        { signal: AbortSignal.timeout(1500) }
      );
      if (res.ok) {
        setBackendRunning(true);
        return true;
      }
    } catch { /* not running */ }
    setBackendRunning(false);
    return false;
  }, [settings.apiPort, setBackendRunning]);

  // ── Start backend ──────────────────────────────────────────────────────────
  const startBackend = useCallback(async () => {
    const alive = await checkBackendHealth();
    if (alive) {
        setBackendRunning(true);
        addMessage({ role: "system", text: "▶ Backend already running" });
        return;
    }

    try {
        await invoke("start_backend", {
            sttMode:     settings.sttMode,
            ollamaModel: settings.ollamaModel,
            ttsVoice:    settings.ttsVoice,
            ttsEngine:   settings.ttsEngine,
            apiPort:     settings.apiPort,
        });

        addMessage({ role: "system", text: "⏳ Starting backend…" });

        // Poll every second for up to 30 seconds
        for (let i = 0; i < 30; i++) {
            await new Promise(r => setTimeout(r, 1000));
            const ok = await checkBackendHealth();
            if (ok) {
                addMessage({ role: "system", text: "▶ Backend started" });
                return;
            }
        }
        addMessage({ role: "system", text: "⚠ Backend is slow to start — check terminal for errors" });
    } catch (err) {
        addMessage({ role: "system", text: `✗ Failed to start: ${err}` });
    }
}, [settings, checkBackendHealth, setBackendRunning, addMessage]);

  // ── Stop backend ───────────────────────────────────────────────────────────
  const stopBackend = useCallback(async () => {
    try {
      await invoke("stop_backend");
      addMessage({ role: "system", text: "■ Backend stopped" });
    } catch {
      // Sidecar not running — just mark as stopped
      addMessage({ role: "system", text: "■ Backend disconnected" });
    }
    setBackendRunning(false);
  }, [setBackendRunning, addMessage]);

  // ── Fetch conversation history ─────────────────────────────────────────────
  const fetchHistory = useCallback(async () => {
    try {
      const res = await fetch(
        `http://127.0.0.1:${settings.apiPort}/api/history?n=50`
      );
      if (!res.ok) return;
      const data: HistoryResponse = await res.json();
      setHistory(data.turns);
    } catch { /* backend not running yet */ }
  }, [settings.apiPort, setHistory]);

  // ── Open config folder ─────────────────────────────────────────────────────
  const openConfigFolder = useCallback(async () => {
    try {
      await invoke("open_config_folder");
    } catch { /* noop */ }
  }, []);

  // ── Poll health every 3s to auto-detect backend start/stop ────────────────
  useEffect(() => {
    checkBackendHealth();
    const interval = setInterval(checkBackendHealth, 3000);
    return () => clearInterval(interval);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [settings.apiPort]);

  return {
    startBackend,
    stopBackend,
    fetchHistory,
    checkBackendHealth,
    openConfigFolder,
    backendRunning,
  };
}