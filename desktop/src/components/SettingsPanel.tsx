import { useState } from "react";
import {
  Settings, Server, Mic, Volume2,
  FolderOpen, RotateCcw, ExternalLink, Power, Radio,
} from "lucide-react";
import { useSettingsStore, useAgentStore } from "@/store/agentStore";
import { useAgent } from "@/hooks/useAgent";
import { OLLAMA_MODELS, TTS_VOICES } from "@/types";
import clsx from "clsx";

type Tab = "backend" | "voice" | "appearance";

const TABS: { id: Tab; label: string; icon: React.ReactNode }[] = [
  { id: "backend",    label: "Backend", icon: <Server   size={14} /> },
  { id: "voice",      label: "Voice",   icon: <Mic      size={14} /> },
  { id: "appearance", label: "UI",      icon: <Settings size={14} /> },
];

export function SettingsPanel() {
  const { settings, updateSettings, resetSettings } = useSettingsStore();
  const { backendRunning }                          = useAgentStore();
  const { startBackend, stopBackend, openConfigFolder } = useAgent();
  const [activeTab, setActiveTab] = useState<Tab>("voice");

  const toggleAgent = () => backendRunning ? stopBackend() : startBackend();

  const switchVoice = async (key: string) => {
    const was = backendRunning;
    if (was) await stopBackend();
    updateSettings({ ttsVoice: key });
    if (was) await startBackend();
  };

  const switchEngine = async (eng: typeof settings.ttsEngine) => {
    const was = backendRunning;
    if (was) await stopBackend();
    updateSettings({ ttsEngine: eng });
    if (was) await startBackend();
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center gap-2 px-5 py-4 border-b" style={{ borderColor: "var(--border)" }}>
        <Settings size={16} style={{ color: "var(--blue)" }} />
        <span className="font-semibold text-sm">Settings</span>
      </div>

      <div className="flex gap-1 px-4 pt-3 pb-0">
        {TABS.map((t) => (
          <button key={t.id}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium transition-all no-drag"
            style={{
              background: activeTab === t.id ? "rgba(14,138,240,.15)" : "transparent",
              border:     activeTab === t.id ? "1px solid rgba(14,138,240,.25)" : "1px solid transparent",
              color:      activeTab === t.id ? "var(--blue)" : "var(--muted)",
            }}
            onClick={() => setActiveTab(t.id)}
          >
            {t.icon}{t.label}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-4">

        {/* ─────────── VOICE TAB ─────────── */}
        {activeTab === "voice" && (<>

          <Section title="Voice Agent" icon={<Radio size={14} />}>
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium" style={{ color: "var(--text)" }}>
                  {backendRunning ? "Agent is running" : "Agent is stopped"}
                </p>
                <p className="text-xs mt-0.5" style={{ color: "var(--muted)" }}>
                  {backendRunning ? "Samantha is listening and ready" : "Start to enable voice features"}
                </p>
              </div>
              <button
                className={clsx("agent-toggle no-drag", backendRunning && "agent-toggle--on")}
                onClick={toggleAgent}
                aria-pressed={backendRunning}
              >
                <Power size={14} />
                <span>{backendRunning ? "ON" : "OFF"}</span>
              </button>
            </div>
            <div className="flex items-center gap-2 mt-3 px-3 py-2 rounded-lg"
              style={{ background: "var(--bg)", border: "1px solid var(--border)" }}>
              <span className="w-2 h-2 rounded-full flex-shrink-0" style={{
                background: backendRunning ? "var(--teal)" : "#444",
                boxShadow:  backendRunning ? "0 0 6px var(--teal)" : "none",
                transition: "all .3s",
              }} />
              <span className="text-xs" style={{ color: "var(--muted)" }}>
                {backendRunning
                  ? `Active · ${settings.ollamaModel} · ${settings.ttsEngine} TTS`
                  : "Idle — click ON to start"}
              </span>
            </div>
          </Section>

          <Section title="Voice" icon={<Mic size={14} />}>
            <div className="grid grid-cols-1 gap-1.5">
              {TTS_VOICES.map((v) => {
                const active = settings.ttsVoice === v.key;
                return (
                  <button key={v.key}
                    className="flex items-center justify-between px-3 py-2.5 rounded-lg text-left transition-all no-drag"
                    style={{
                      background: active ? "rgba(240,64,158,.08)" : "var(--card)",
                      border:     active ? "1px solid rgba(240,64,158,.25)" : "1px solid var(--border)",
                    }}
                    onClick={() => switchVoice(v.key)}
                  >
                    <div className="flex items-center gap-2">
                      <span className="w-2 h-2 rounded-full flex-shrink-0" style={{
                        background: active ? "var(--pink)" : "transparent",
                        border:     active ? "none" : "1px solid var(--border)",
                        boxShadow:  active ? "0 0 5px var(--pink)" : "none",
                      }} />
                      <span className="text-sm font-medium"
                        style={{ color: active ? "var(--pink)" : "var(--text)" }}>
                        {v.name}
                      </span>
                    </div>
                    <div className="flex items-center gap-1.5">
                      <span className="text-xs" style={{ color: "var(--muted)" }}>{v.gender}</span>
                      <span className="text-xs px-1.5 py-0.5 rounded font-mono"
                        style={{ background: "rgba(255,255,255,.05)", color: "var(--muted)" }}>
                        {v.locale}
                      </span>
                    </div>
                  </button>
                );
              })}
            </div>
            {backendRunning && (
              <p className="text-xs mt-2" style={{ color: "var(--teal)" }}>
                ✓ Switching voice restarts the agent automatically.
              </p>
            )}
          </Section>

          <Section title="TTS Engine" icon={<Volume2 size={14} />}>
            <div className="grid grid-cols-2 gap-1.5">
              {(["edge", "piper", "pyttsx3", "none"] as const).map((eng) => (
                <button key={eng}
                  className="px-3 py-2 rounded-lg text-xs font-medium transition-all no-drag"
                  style={{
                    background: settings.ttsEngine === eng ? "rgba(124,77,255,.12)" : "var(--card)",
                    border:     settings.ttsEngine === eng ? "1px solid rgba(124,77,255,.3)" : "1px solid var(--border)",
                    color:      settings.ttsEngine === eng ? "var(--purple)" : "var(--muted)",
                  }}
                  onClick={() => switchEngine(eng)}
                >
                  {{ edge: "🌐 Edge TTS", piper: "🤖 Piper", pyttsx3: "💻 pyttsx3", none: "🔇 Silent" }[eng]}
                </button>
              ))}
            </div>
            <p className="text-xs mt-2" style={{ color: "var(--muted)" }}>
              Edge TTS — best quality, needs internet once.&ensp;Piper — fully offline.
            </p>
          </Section>

          <Section title="Input Mode" icon={<Mic size={14} />}>
            <div className="grid grid-cols-3 gap-1.5">
              {(["rust_bridge", "voice", "text"] as const).map((mode) => (
                <button key={mode}
                  className="px-3 py-2 rounded-lg text-xs font-medium transition-all no-drag"
                  style={{
                    background: settings.sttMode === mode ? "rgba(0,201,167,.1)" : "var(--card)",
                    border:     settings.sttMode === mode ? "1px solid rgba(0,201,167,.3)" : "1px solid var(--border)",
                    color:      settings.sttMode === mode ? "var(--teal)" : "var(--muted)",
                  }}
                  onClick={() => updateSettings({ sttMode: mode })}
                >
                  {{ rust_bridge: "🦀 Rust", voice: "🎙 Python", text: "⌨️ Text" }[mode]}
                </button>
              ))}
            </div>
            <p className="text-xs mt-2" style={{ color: "var(--muted)" }}>
              Rust Bridge = lowest latency.&ensp;Python = fallback.&ensp;Text = no mic.
            </p>
          </Section>
        </>)}

        {/* ─────────── BACKEND TAB ─────────── */}
        {activeTab === "backend" && (<>
          <Section title="LLM Model" icon={<Server size={14} />}>
            <p className="text-xs mb-2" style={{ color: "var(--muted)" }}>
              Run <code>ollama pull &lt;name&gt;</code> first.
            </p>
            <div className="grid grid-cols-1 gap-1.5">
              {OLLAMA_MODELS.map((m) => (
                <button key={m.env}
                  className="flex items-center justify-between px-3 py-2 rounded-lg text-left transition-all no-drag"
                  style={{
                    background: settings.ollamaModel === m.env ? "rgba(14,138,240,.1)" : "var(--card)",
                    border:     settings.ollamaModel === m.env ? "1px solid rgba(14,138,240,.25)" : "1px solid var(--border)",
                  }}
                  onClick={() => updateSettings({ ollamaModel: m.env })}
                >
                  <div>
                    <span className="text-sm font-medium"
                      style={{ color: settings.ollamaModel === m.env ? "var(--blue)" : "var(--text)" }}>
                      {m.name}
                    </span>
                    <span className="text-xs ml-2" style={{ color: "var(--muted)" }}>{m.size}</span>
                  </div>
                  <span className="text-xs px-2 py-0.5 rounded-full"
                    style={{ background: "rgba(255,255,255,.05)", color: "var(--muted)" }}>
                    {m.tag}
                  </span>
                </button>
              ))}
            </div>
          </Section>

          <Section title="API Port">
            <div className="flex items-center gap-2">
              <input type="number" className="no-drag"
                style={{
                  background: "var(--card)", border: "1px solid var(--border)",
                  borderRadius: 8, color: "var(--text)",
                  padding: "7px 12px", fontSize: 13, width: 110, outline: "none",
                }}
                value={settings.apiPort}
                onChange={(e) => updateSettings({ apiPort: +e.target.value })}
                min={1024} max={65535}
              />
              <span className="text-xs" style={{ color: "var(--muted)" }}>Default: 7799</span>
            </div>
          </Section>

          <Section title="Backend Control">
            <div className="flex gap-2 flex-wrap">
              <button
                className={clsx("no-drag", backendRunning ? "btn-danger" : "btn-primary")}
                onClick={toggleAgent}
              >
                {backendRunning ? "■ Stop Backend" : "▶ Start Backend"}
              </button>
              <button className="btn-secondary no-drag" onClick={openConfigFolder}>
                <FolderOpen size={13} />Config Folder
              </button>
            </div>
          </Section>
        </>)}

        {/* ─────────── APPEARANCE TAB ─────────── */}
        {activeTab === "appearance" && (<>
          <Section title="Theme">
            <div className="flex gap-2">
              {(["dark", "light"] as const).map((t) => (
                <button key={t}
                  className="px-4 py-2 rounded-lg text-sm font-medium transition-all no-drag"
                  style={{
                    background: settings.theme === t ? "rgba(14,138,240,.1)" : "var(--card)",
                    border:     settings.theme === t ? "1px solid rgba(14,138,240,.25)" : "1px solid var(--border)",
                    color:      settings.theme === t ? "var(--blue)" : "var(--muted)",
                  }}
                  onClick={() => {
                    updateSettings({ theme: t });
                    document.documentElement.setAttribute("data-theme", t);
                  }}
                >
                  {t === "dark" ? "🌙 Dark" : "☀️ Light"}
                </button>
              ))}
            </div>
          </Section>

          <Section title="Autostart">
            <label className="flex items-center gap-3 cursor-pointer no-drag">
              <input type="checkbox"
                checked={settings.autostart}
                onChange={(e) => updateSettings({ autostart: e.target.checked })}
                className="w-4 h-4 rounded"
              />
              <div>
                <p className="text-sm">Launch on system startup</p>
                <p className="text-xs" style={{ color: "var(--muted)" }}>Opens Samantha when you log in</p>
              </div>
            </label>
          </Section>
        </>)}
      </div>

      <div className="px-4 pb-4 pt-2 border-t flex items-center justify-between"
        style={{ borderColor: "var(--border)" }}>
        <button className="btn-secondary text-xs px-3 py-1.5 no-drag" onClick={resetSettings}>
          <RotateCcw size={11} />Reset
        </button>
        <a href="https://zenonai.net" target="_blank" rel="noopener noreferrer"
          className="flex items-center gap-1 text-xs no-drag" style={{ color: "var(--muted)" }}>
          zenonai.net <ExternalLink size={10} />
        </a>
      </div>
    </div>
  );
}

function Section({ title, icon, children }: {
  title: string; icon?: React.ReactNode; children: React.ReactNode;
}) {
  return (
    <div className="rounded-xl p-4" style={{ background: "var(--card)", border: "1px solid var(--border)" }}>
      <div className="flex items-center gap-1.5 mb-3">
        {icon && <span style={{ color: "var(--blue)" }}>{icon}</span>}
        <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: "var(--muted)" }}>
          {title}
        </h3>
      </div>
      {children}
    </div>
  );
}
