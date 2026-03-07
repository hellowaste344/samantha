import { MessageSquare, Clock, Settings, Power, Github, Globe } from "lucide-react";
import { useAgentStore } from "@/store/agentStore";
import { useAgent } from "@/hooks/useAgent";
import clsx from "clsx";

type View = "chat" | "history" | "settings";

export function Sidebar() {
  const { activeView, setActiveView, connected, agentState, backendRunning } = useAgentStore();
  const { startBackend, stopBackend } = useAgent();

  const navItems: { id: View; label: string; icon: React.ReactNode }[] = [
    { id: "chat",     label: "Chat",     icon: <MessageSquare size={16} /> },
    { id: "history",  label: "History",  icon: <Clock size={16} /> },
    { id: "settings", label: "Settings", icon: <Settings size={16} /> },
  ];

  const stateColor =
    agentState === "listening" ? "var(--teal)"   :
    agentState === "thinking"  ? "var(--blue)"   :
    agentState === "acting"    ? "var(--purple)"  :
    agentState === "speaking"  ? "var(--pink)"   :
    connected                  ? "#44445a"       :
    "#555";

  return (
    <div
      className="flex flex-col w-[56px] border-r h-full"
      style={{ background: "var(--card)", borderColor: "var(--border)" }}
    >
      {/* Logo */}
      <div className="drag-region flex items-center justify-center h-12 border-b" style={{ borderColor: "var(--border)" }}>
        <div
          className="w-8 h-8 rounded-lg flex items-center justify-center text-sm font-bold"
          style={{ background: "linear-gradient(135deg, var(--blue), var(--teal))" }}
        >
          S
        </div>
      </div>

      {/* Nav */}
      <nav className="flex-1 flex flex-col items-center gap-1 py-3">
        {navItems.map((item) => (
          <button
            key={item.id}
            data-tip={item.label}
            className={clsx(
              "w-10 h-10 rounded-xl flex items-center justify-center transition-all no-drag",
              activeView === item.id ? "text-white" : ""
            )}
            style={{
              background: activeView === item.id ? "rgba(14,138,240,.15)" : "transparent",
              border:     activeView === item.id ? "1px solid rgba(14,138,240,.2)" : "1px solid transparent",
              color:      activeView === item.id ? "var(--blue)" : "var(--muted)",
            }}
            onClick={() => setActiveView(item.id)}
          >
            {item.icon}
          </button>
        ))}
      </nav>

      {/* Bottom controls */}
      <div className="flex flex-col items-center gap-2 py-3 border-t" style={{ borderColor: "var(--border)" }}>
        {/* Connection status dot */}
        <div
          className="w-2 h-2 rounded-full"
          data-tip={agentState}
          style={{ background: stateColor, transition: "background 0.3s" }}
        />

        {/* Power / backend toggle */}
        <button
          data-tip={backendRunning ? "Stop backend" : "Start backend"}
          className="w-8 h-8 rounded-lg flex items-center justify-center transition-all no-drag"
          style={{
            background: backendRunning ? "rgba(240,64,158,.1)" : "rgba(255,255,255,.04)",
            border:     backendRunning ? "1px solid rgba(240,64,158,.2)" : "1px solid var(--border)",
            color:      backendRunning ? "var(--pink)" : "var(--muted)",
          }}
          onClick={backendRunning ? stopBackend : startBackend}
        >
          <Power size={14} />
        </button>

        {/* External links */}
        <a
          href="https://github.com/hellowaste344"
          target="_blank"
          rel="noopener noreferrer"
          data-tip="GitHub"
          className="w-8 h-8 rounded-lg flex items-center justify-center transition-all no-drag"
          style={{
            background: "rgba(255,255,255,.04)",
            border: "1px solid var(--border)",
            color: "var(--muted)",
          }}
        >
          <Github size={13} />
        </a>

        <a
          href="https://zenonai.net"
          target="_blank"
          rel="noopener noreferrer"
          data-tip="zenonai.net"
          className="w-8 h-8 rounded-lg flex items-center justify-center transition-all no-drag"
          style={{
            background: "rgba(255,255,255,.04)",
            border: "1px solid var(--border)",
            color: "var(--muted)",
          }}
        >
          <Globe size={13} />
        </a>
      </div>
    </div>
  );
}
