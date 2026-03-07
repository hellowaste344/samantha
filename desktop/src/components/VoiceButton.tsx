import { Mic, MicOff, Square } from "lucide-react";
import { useAgentStore } from "@/store/agentStore";

interface Props {
  disabled?: boolean;
}

export function VoiceButton({ disabled }: Props) {
  const { agentState, connected } = useAgentStore();

  const isListening = agentState === "listening";
  const isBusy      = agentState === "thinking" || agentState === "acting" || agentState === "speaking";
  const isDisabled  = !connected || disabled;

  return (
    <div className="flex items-center justify-center">
      <div className="relative">
        {/* Pulse ring when listening */}
        {isListening && (
          <>
            <div
              className="absolute inset-0 rounded-full"
              style={{
                background: "rgba(14,138,240,.15)",
                animation: "pulseRing 1.5s ease-out infinite",
                transform: "scale(1.4)",
              }}
            />
            <div
              className="absolute inset-0 rounded-full"
              style={{
                background: "rgba(0,201,167,.08)",
                animation: "pulseRing 1.5s ease-out 0.5s infinite",
                transform: "scale(1.7)",
              }}
            />
          </>
        )}

        <button
          className="relative w-14 h-14 rounded-full flex items-center justify-center transition-all duration-200"
          disabled={isDisabled || isBusy}
          style={{
            background: isListening
              ? "linear-gradient(135deg, var(--blue), var(--teal))"
              : isBusy
                ? "linear-gradient(135deg, var(--purple), var(--pink))"
                : isDisabled
                  ? "rgba(255,255,255,.04)"
                  : "linear-gradient(135deg, rgba(14,138,240,.2), rgba(0,201,167,.15))",
            border: isListening
              ? "2px solid rgba(14,138,240,.6)"
              : "2px solid var(--border)",
            cursor: isDisabled || isBusy ? "not-allowed" : "pointer",
            boxShadow: isListening ? "0 0 24px rgba(14,138,240,.4)" : "none",
            opacity: isDisabled ? 0.4 : 1,
          }}
          title={
            isListening ? "Listening…" :
            isBusy      ? "Samantha is busy…" :
            isDisabled  ? "Connect backend first" :
            "Voice is managed by the backend"
          }
        >
          {isBusy ? (
            <Square size={20} style={{ color: "var(--pink)" }} />
          ) : isListening ? (
            <Mic size={22} color="#fff" />
          ) : (
            <MicOff size={20} style={{ color: isDisabled ? "var(--muted)" : "var(--blue)" }} />
          )}
        </button>
      </div>
    </div>
  );
}
