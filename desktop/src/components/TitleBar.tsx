import { Minus, Square, X } from "lucide-react";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { useAgentStore } from "@/store/agentStore";

const STATE_LABELS: Record<string, string> = {
  disconnected: "",
  connecting:   "Connecting…",
  idle:         "",
  listening:    "Listening",
  thinking:     "Thinking…",
  acting:       "Working…",
  speaking:     "Speaking",
};

export function TitleBar() {
  const { agentState } = useAgentStore();
  const label = STATE_LABELS[agentState] || "";

  const minimize = () => getCurrentWindow().minimize();
  const maximize = () => getCurrentWindow().toggleMaximize();
  const close    = () => getCurrentWindow().close();

  return (
    <div
      className="drag-region flex items-center justify-between h-10 px-3 border-b select-none flex-shrink-0"
      style={{ background: "var(--card)", borderColor: "var(--border)" }}
    >
      {/* Left: app identity */}
      <div className="flex items-center gap-2">
        <div
          className="w-5 h-5 rounded flex items-center justify-center text-xs font-bold"
          style={{ background: "linear-gradient(135deg, var(--blue), var(--teal))" }}
        >
          S
        </div>
        <span className="text-sm font-semibold">Samantha</span>
        {label && (
          <span className="text-xs px-2 py-0.5 rounded-full" style={{ background: "rgba(14,138,240,.1)", color: "var(--blue)" }}>
            {label}
          </span>
        )}
      </div>

      {/* Right: window controls */}
      <div className="flex items-center gap-1 no-drag">
        <button
          className="w-7 h-7 rounded-lg flex items-center justify-center transition-all"
          style={{ color: "var(--muted)" }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,.08)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          onClick={minimize}
        >
          <Minus size={12} />
        </button>
        <button
          className="w-7 h-7 rounded-lg flex items-center justify-center transition-all"
          style={{ color: "var(--muted)" }}
          onMouseEnter={(e) => (e.currentTarget.style.background = "rgba(255,255,255,.08)")}
          onMouseLeave={(e) => (e.currentTarget.style.background = "transparent")}
          onClick={maximize}
        >
          <Square size={11} />
        </button>
        <button
          className="w-7 h-7 rounded-lg flex items-center justify-center transition-all"
          style={{ color: "var(--muted)" }}
          onMouseEnter={(e) => { e.currentTarget.style.background = "rgba(240,64,158,.2)"; e.currentTarget.style.color = "var(--pink)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; e.currentTarget.style.color = "var(--muted)"; }}
          onClick={close}
        >
          <X size={13} />
        </button>
      </div>
    </div>
  );
}
