import { useCallback, useEffect } from "react";
import { invoke } from "@tauri-apps/api/core";
import { useAgentStore } from "@/store/agentStore";
import { useSettingsStore } from "@/store/agentStore";
import type { HistoryResponse } from "@/types";

export function useAgent() {
  const { setBackendRunning, setHistory, addMessage, backendRunning } = useAgentStore();
  const { settings } = useSettingsStore();

  // ── Start backend (Tauri sidecar) ──────────────────────────────────────────
  const startBackend = useCallback(async () => {
    try {
      await invoke("start_backend", {
        sttMode:    settings.sttMode,
        ollamaModel:settings.ollamaModel,
        ttsVoice:   settings.ttsVoice,
        ttsEngine:  settings.ttsEngine,
        apiPort:    settings.apiPort,
      });
      setBackendRunning(true);
      addMessage({ role: "system", text: "▶ Backend started" });
    } catch (err) {
      addMessage({ role: "system", text: `✗ Failed to start backend: ${err}` });
    }
  }, [settings, setBackendRunning, addMessage]);

  // ── Stop backend ───────────────────────────────────────────────────────────
  const stopBackend = useCallback(async () => {
    try {
      await invoke("stop_backend");
      setBackendRunning(false);
      addMessage({ role: "system", text: "■ Backend stopped" });
    } catch (err) {
      addMessage({ role: "system", text: `✗ Failed to stop backend: ${err}` });
    }
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
    } catch {
      /* backend not running yet */
    }
  }, [settings.apiPort, setHistory]);

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
    } catch {
      /* not running */
    }
    setBackendRunning(false);
    return false;
  }, [settings.apiPort, setBackendRunning]);

  // ── Open settings folder ───────────────────────────────────────────────────
  const openConfigFolder = useCallback(async () => {
    try {
      await invoke("open_config_folder");
    } catch {/* noop */}
  }, []);

  // ── Check health on apiPort change ────────────────────────────────────────
  useEffect(() => {
    checkBackendHealth();
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
