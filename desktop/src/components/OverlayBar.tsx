import { useState, useEffect, useRef, useCallback } from "react";
<<<<<<< HEAD
import { invoke } from "@tauri-apps/api/core";
=======
import { invoke } from "@tauri-apps/api/core";  // OverlayBar.tsx, App.tsx, etc.
import { getCurrentWindow } from "@tauri-apps/api/window";
>>>>>>> 8b37e69bd68cde7857316aa08a0ca46ea483029f
import { listen } from "@tauri-apps/api/event";
import {
  Settings, Minus, ChevronRight,
  Eye, EyeOff, Send, Power,
  Mic, MicOff, RefreshCw,
} from "lucide-react";
import { useAgentStore, useSettingsStore } from "@/store/agentStore";
import { useAgent } from "@/hooks/useAgent";
import clsx from "clsx";
import type { AgentState } from "@/types";
import { useWebSocket } from "@/hooks/useWebSocket";
<<<<<<< HEAD

=======
>>>>>>> 8b37e69bd68cde7857316aa08a0ca46ea483029f
type Tab = "chat" | "settings";

const STATE_DOT: Record<AgentState, string> = {
  disconnected: "#333",
  connecting: "#555",
  idle: "#3a3a50",
  listening: "#00c9a7",
  thinking: "#0e8af0",
  acting: "#7c4dff",
  speaking: "#f0409e",
};

const STATE_LABEL: Record<AgentState, string> = {
  disconnected: "Offline",
  connecting: "Connecting…",
  idle: "Ready",
  listening: "Listening",
  thinking: "Thinking…",
  acting: "Working…",
  speaking: "Speaking…",
};

export function OverlayBar() {
<<<<<<< HEAD
  const { agentState, messages, connected } = useAgentStore();
  const { settings, updateSettings } = useSettingsStore();
  const { startBackend, stopBackend, backendRunning, checkBackendHealth } = useAgent();
  useWebSocket();

=======
  const { agentState, messages } = useAgentStore();
  const { settings, updateSettings } = useSettingsStore();
  const { startBackend, stopBackend, backendRunning, checkBackendHealth } = useAgent();
  useWebSocket();
>>>>>>> 8b37e69bd68cde7857316aa08a0ca46ea483029f
  const [tab, setTab] = useState<Tab>("chat");
  const [folded, setFolded] = useState(false);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);
<<<<<<< HEAD
  const [voiceLoading, setVoiceLoading] = useState(false);
=======
>>>>>>> 8b37e69bd68cde7857316aa08a0ca46ea483029f
  const bottomRef = useRef<HTMLDivElement>(null);
  const idleTimer = useRef<ReturnType<typeof setTimeout>>();

  const isActive = ["listening", "speaking", "thinking", "acting"].includes(agentState);
<<<<<<< HEAD
  const isListening = agentState === "listening";
=======
  const connected = useAgentStore(s => s.connected);
>>>>>>> 8b37e69bd68cde7857316aa08a0ca46ea483029f
  const dot = STATE_DOT[agentState];

  // ── Backend events ────────────────────────────────────────────────────────
  useEffect(() => {
    const u1 = listen("backend-started", () => useAgentStore.getState().setBackendRunning(true));
    const u2 = listen("backend-stopped", () => useAgentStore.getState().setBackendRunning(false));
    return () => { u1.then(f => f()); u2.then(f => f()); };
  }, []);

<<<<<<< HEAD
  // ── Resize overlay when folded ────────────────────────────────────────────
=======
>>>>>>> 8b37e69bd68cde7857316aa08a0ca46ea483029f
  useEffect(() => {
    invoke("set_overlay_width", { width: folded ? 50 : 550 }).catch(() => { });
  }, [folded]);

<<<<<<< HEAD
  // ── Health check on mount ─────────────────────────────────────────────────
=======
  // Health check on mount
>>>>>>> 8b37e69bd68cde7857316aa08a0ca46ea483029f
  useEffect(() => { checkBackendHealth(); }, []); // eslint-disable-line

  // ── Auto-scroll ───────────────────────────────────────────────────────────
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // ── Auto-fold after 45s idle ──────────────────────────────────────────────
  useEffect(() => {
    if (idleTimer.current) clearTimeout(idleTimer.current);
    if (!isActive && messages.length > 0) {
      idleTimer.current = setTimeout(() => setFolded(true), 45_000);
    }
    if (isActive) setFolded(false);
    return () => { if (idleTimer.current) clearTimeout(idleTimer.current); };
  }, [isActive, messages.length]);

  // ── Send typed message ────────────────────────────────────────────────────
  const sendText = useCallback(async () => {
    const msg = text.trim();
    if (!msg || sending) return;
    setText("");
    setSending(true);
    try {
      const res = await fetch(`http://127.0.0.1:${settings.apiPort}/api/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: msg }),
      });
      if (!res.ok) {
        useAgentStore.getState().addMessage({ role: "system", text: "✗ Failed to send message" });
      }
    } catch {
      useAgentStore.getState().addMessage({ role: "system", text: "✗ Backend not reachable" });
    }
    setSending(false);
  }, [text, sending, settings.apiPort]);

  const onKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendText(); }
  };

<<<<<<< HEAD
  // ── Voice button handler ──────────────────────────────────────────────────
  const handleVoice = useCallback(async () => {
    if (voiceLoading || (isActive && !isListening)) return;
    setVoiceLoading(true);
    try {
      if (isListening) {
        await fetch(`http://127.0.0.1:${settings.apiPort}/api/listen/stop`, {
          method: "POST",
        });
      } else {
        await fetch(`http://127.0.0.1:${settings.apiPort}/api/listen/start`, {
          method: "POST",
        });
      }
    } catch {
      useAgentStore.getState().addMessage({ role: "system", text: "✗ Voice not available" });
    }
    setVoiceLoading(false);
  }, [voiceLoading, isActive, isListening, settings.apiPort]);
=======
  const reposition = () => invoke("reposition_overlay").catch(() => { });
>>>>>>> 8b37e69bd68cde7857316aa08a0ca46ea483029f

  const reposition = () => invoke("reposition_overlay").catch(() => { });

  // ── Folded pill ───────────────────────────────────────────────────────────
  if (folded) {
    return (
      <div className="ob-pill" onClick={() => setFolded(false)} title="Expand Samantha">
        <span className="ob-pill-dot" style={{ background: dot }} />
        <span className="ob-pill-s">S</span>
        <ChevronRight size={9} className="ob-pill-arrow" />
      </div>
    );
  }

  const recent = messages.slice(-50);

  // ── Full bar ──────────────────────────────────────────────────────────────
  return (
    <div className="ob-root">

      <div className="ob-edge-label" aria-hidden>
        <span>Samantha</span>
      </div>

      <div className="ob-panel">

        {/* Header */}
        <div className="ob-header" data-tauri-drag-region>
          <div className="ob-header-left">
            <span className="ob-status-dot" style={{
              background: dot,
              boxShadow: isActive ? `0 0 8px ${dot}88` : "none",
            }} />
            <span className="ob-title">Samantha</span>
          </div>
          <div className="ob-header-btns">
            <button className="ob-ctrl" onClick={reposition} title="Re-snap to right edge">
              <RefreshCw size={9} />
            </button>
            <button className="ob-ctrl" onClick={() => setFolded(true)} title="Collapse">
              <Minus size={9} />
            </button>
<<<<<<< HEAD
            <button className="ob-ctrl" onClick={() => setFolded(true)} title="Hide">
=======
            <button
              className="ob-ctrl"
              onClick={() => setFolded(true)}
              title="Hide"
            >
>>>>>>> 8b37e69bd68cde7857316aa08a0ca46ea483029f
              <ChevronRight size={9} />
            </button>
          </div>
        </div>

        {/* Status + power row */}
        <div className="ob-status-row">
          <span className="ob-state-label">{STATE_LABEL[agentState]}</span>
          <button
            className={clsx("ob-power-btn", backendRunning && "ob-power-btn--on")}
            onClick={() => backendRunning ? stopBackend() : startBackend()}
            title={backendRunning ? "Stop agent" : "Start agent"}
          >
            <Power size={10} />
            <span>{backendRunning ? "ON" : "OFF"}</span>
          </button>
        </div>

        {/* Waveform */}
        {isActive && (
          <div className="ob-wave" aria-hidden>
            {[.35, .6, .9, .7, 1, .75, .5, .85, .4, .65, .45].map((h, i) => (
              <span key={i} className="ob-wave-bar" style={{
                animationDelay: `${i * 0.09}s`,
                height: `${h * 22}px`,
                background: dot,
              }} />
            ))}
          </div>
        )}

        {/* Tabs */}
        <div className="ob-tabs" role="tablist">
          <button
            role="tab"
            aria-selected={tab === "chat"}
            className={clsx("ob-tab", tab === "chat" && "ob-tab--on")}
            onClick={() => setTab("chat")}
          >
            {backendRunning ? <Mic size={10} /> : <MicOff size={10} />}
            Chat
          </button>
          <button
            role="tab"
            aria-selected={tab === "settings"}
            className={clsx("ob-tab", tab === "settings" && "ob-tab--on")}
            onClick={() => setTab("settings")}
          >
            <Settings size={10} />
            Settings
          </button>
        </div>

        {/* ── Chat panel ────────────────────────────────────────── */}
        {tab === "chat" && (
          <div className="ob-chat" role="tabpanel">
            <div className="ob-messages">
              {recent.length === 0
                ? <p className="ob-empty">
<<<<<<< HEAD
                  {backendRunning ? "Say something or type below…" : "Start the agent to begin"}
=======
                  {backendRunning
                    ? "Say something or type below…"
                    : "Start the agent to begin"}
>>>>>>> 8b37e69bd68cde7857316aa08a0ca46ea483029f
                </p>
                : recent.map(m => (
                  <div key={m.id} className={clsx(
                    "ob-msg",
                    m.role === "user" && "ob-msg--user",
                    m.role === "assistant" && "ob-msg--ai",
                    m.role === "system" && "ob-msg--sys",
                  )}>
                    {m.text}
                  </div>
                ))
              }
              <div ref={bottomRef} />
            </div>

            {/* Input row */}
            <div className="ob-input-row">

              {/* Voice button */}
              <button
                className={clsx(
                  "ob-voice-btn",
                  isListening && "ob-voice-btn--listening",
                  voiceLoading && "ob-voice-btn--loading",
                )}
                onClick={handleVoice}
                disabled={voiceLoading || (isActive && !isListening) || !backendRunning}
                title={
                  !backendRunning ? "Start agent first" :
                    isListening ? "Click to stop" :
                      isActive ? "Busy…" :
                        "Click to speak"
                }
              >
                {voiceLoading
                  ? <span className="lp-spinner" style={{ borderTopColor: "white", borderColor: "rgba(255,255,255,0.2)" }} />
                  : isListening
                    ? <Mic size={13} color="white" />
                    : <MicOff size={13} style={{ color: !backendRunning ? "rgba(255,255,255,0.2)" : "rgba(255,255,255,0.6)" }} />
                }
              </button>

              {/* Text input */}
              <textarea
                className="ob-textarea"
                rows={1}
                value={text}
                onChange={e => setText(e.target.value)}
                onKeyDown={onKey}
                placeholder={
<<<<<<< HEAD
                  !backendRunning ? "Start agent first…" :
                    isActive ? "Busy…" :
                      "Message…"
                }
                disabled={isActive || sending || !backendRunning}
=======
                  !backendRunning ? "Start agent first…"
                    : isActive ? "Busy…"
                      : "Message…"
                }
                disabled={isActive || sending}
>>>>>>> 8b37e69bd68cde7857316aa08a0ca46ea483029f
              />

              {/* Send button */}
              <button
                className="ob-send"
                onClick={sendText}
<<<<<<< HEAD
                disabled={!text.trim() || isActive || sending || !backendRunning}
=======
                disabled={!text.trim() || isActive || sending}
>>>>>>> 8b37e69bd68cde7857316aa08a0ca46ea483029f
                aria-label="Send"
              >
                <Send size={11} />
              </button>
            </div>
          </div>
        )}

        {/* ── Settings panel ────────────────────────────────────── */}
        {tab === "settings" && (
          <div className="ob-settings" role="tabpanel">
            <ObRow label="Agent">
              <button
                className={clsx("ob-toggle", backendRunning && "ob-toggle--on")}
                onClick={() => backendRunning ? stopBackend() : startBackend()}
              >
                <Power size={9} /> {backendRunning ? "ON" : "OFF"}
              </button>
            </ObRow>
            <ObRow label="Vision">
              <button
                className={clsx("ob-toggle", settings.visionEnabled && "ob-toggle--on")}
                onClick={() => updateSettings({ visionEnabled: !settings.visionEnabled })}
              >
                {settings.visionEnabled ? <Eye size={9} /> : <EyeOff size={9} />}
                {settings.visionEnabled ? "ON" : "OFF"}
              </button>
            </ObRow>
            <ObRow label="Voice">
              <span className="ob-val">{settings.ttsVoice || "—"}</span>
            </ObRow>
            <ObRow label="Engine">
              <span className="ob-val">{settings.ttsEngine || "—"}</span>
            </ObRow>
            <ObRow label="Model">
              <span className="ob-val">{settings.ollamaModel || "—"}</span>
            </ObRow>
            <button className="ob-open-main" onClick={() => invoke("show_main_window")}>
              Open Main Window ↗
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function ObRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="ob-row">
      <span className="ob-row-label">{label}</span>
      {children}
    </div>
  );
}