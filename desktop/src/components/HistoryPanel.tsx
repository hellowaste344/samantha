import { useEffect } from "react";
import { Clock, RefreshCw } from "lucide-react";
import { useAgentStore } from "@/store/agentStore";
import { useAgent } from "@/hooks/useAgent";

export function HistoryPanel() {
  const { history } = useAgentStore();
  const { fetchHistory } = useAgent();

  useEffect(() => {
    fetchHistory();
  }, [fetchHistory]);

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between px-5 py-4 border-b" style={{ borderColor: "var(--border)" }}>
        <div className="flex items-center gap-2">
          <Clock size={16} style={{ color: "var(--blue)" }} />
          <span className="font-semibold text-sm">Conversation History</span>
        </div>
        <button
          className="btn-secondary px-3 py-1.5 text-xs no-drag"
          onClick={fetchHistory}
        >
          <RefreshCw size={12} />
          Refresh
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-4 py-3 space-y-2">
        {history.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full gap-2" style={{ color: "var(--muted)" }}>
            <Clock size={32} strokeWidth={1} />
            <p className="text-sm">No history yet</p>
            <p className="text-xs">Start a conversation to see history here</p>
          </div>
        ) : (
          [...history].reverse().map((turn, i) => (
            <div
              key={i}
              className="rounded-xl p-3 space-y-2 transition-all hover:scale-[1.005]"
              style={{ background: "var(--card)", border: "1px solid var(--border)" }}
            >
              <div className="flex items-start gap-2">
                <div
                  className="w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5"
                  style={{ background: "linear-gradient(135deg, var(--blue), var(--teal))" }}
                >
                  Y
                </div>
                <p className="text-sm" style={{ color: "var(--text)" }}>{turn.user}</p>
              </div>
              <div className="flex items-start gap-2">
                <div
                  className="w-5 h-5 rounded-full flex items-center justify-center text-xs font-bold flex-shrink-0 mt-0.5"
                  style={{ background: "linear-gradient(135deg, var(--purple), var(--pink))" }}
                >
                  S
                </div>
                <p className="text-sm" style={{ color: "var(--muted)" }}>{turn.agent}</p>
              </div>
              <p className="text-xs" style={{ color: "var(--muted)", opacity: 0.6 }}>
                {new Date(turn.ts).toLocaleString()}
              </p>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
