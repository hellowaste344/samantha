import { useAgentStore } from "@/store/agentStore";
import type { AgentState } from "@/types";

const STATE_LABELS: Record<AgentState, string> = {
  disconnected: "Disconnected",
  connecting:   "Connecting…",
  idle:         "Ready",
  listening:    "Listening…",
  thinking:     "Thinking…",
  acting:       "Acting…",
  speaking:     "Speaking…",
};

const STATE_COLORS: Record<AgentState, string> = {
  disconnected: "#555",
  connecting:   "var(--blue)",
  idle:         "#44445a",
  listening:    "var(--teal)",
  thinking:     "var(--blue)",
  acting:       "var(--purple)",
  speaking:     "var(--pink)",
};

export function StatusBar() {
  const { agentState, connected, agentStatus } = useAgentStore();

  return (
    <div
      className="flex items-center justify-between px-4 py-2 border-t"
      style={{ borderColor: "var(--border)", background: "var(--card)" }}
    >
      {/* Left: state indicator */}
      <div className="flex items-center gap-2">
        <span
          className="status-dot"
          style={{ background: STATE_COLORS[agentState] }}
        />
        <span style={{ color: "var(--muted)", fontSize: 12 }}>
          {STATE_LABELS[agentState]}
        </span>

        {agentState === "listening" && (
          <div className="flex items-end gap-[2px] h-4">
            {[1, 2, 3, 4, 5].map((i) => (
              <div
                key={i}
                className="wave-bar"
                style={{ height: `${8 + Math.random() * 8}px`, animationDelay: `${i * 0.1}s` }}
              />
            ))}
          </div>
        )}
      </div>

      {/* Center: model info */}
      {agentStatus?.llm_model && (
        <span style={{ color: "var(--muted)", fontSize: 11 }}>
          <code>{agentStatus.llm_model}</code>
        </span>
      )}

      {/* Right: connection badge */}
      <div className="flex items-center gap-1.5">
        <div
          className="w-1.5 h-1.5 rounded-full"
          style={{ background: connected ? "var(--teal)" : "#555" }}
        />
        <span style={{ color: "var(--muted)", fontSize: 11 }}>
          {connected ? "Connected" : "Offline"}
        </span>
      </div>
    </div>
  );
}
