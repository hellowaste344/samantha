import { useEffect, useRef, useState } from "react";
import { Send } from "lucide-react";
import { useAgentStore } from "@/store/agentStore";
import { MessageBubble } from "./MessageBubble";
import { VoiceButton } from "./VoiceButton";
import { useSettingsStore } from "@/store/agentStore";

export function ChatView() {
  const { messages, agentState, connected } = useAgentStore();
  const { settings } = useSettingsStore();
  const scrollRef = useRef<HTMLDivElement>(null);
  const [text, setText] = useState("");
  const [sending, setSending] = useState(false);

  // Auto-scroll on new message
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const sendTextMessage = async () => {
    if (!text.trim() || !connected || sending) return;
    const msg = text.trim();
    setText("");
    setSending(true);
    try {
      await fetch(`http://127.0.0.1:${settings.apiPort}/api/chat`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ text: msg }),
      });
    } catch {
      /* WS will surface any errors */
    }
    setSending(false);
  };

  const handleKey = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendTextMessage();
    }
  };

  const isBusy = agentState === "thinking" || agentState === "acting" || agentState === "speaking";

  return (
    <div className="flex flex-col h-full">
      {/* ── Hero header (shown when no messages) ─────────────── */}
      {messages.length === 0 && (
        <div className="flex-1 flex flex-col items-center justify-center gap-6 px-8 animate-fade-in">
          {/* Orbs */}
          <div className="relative w-24 h-24">
            <div className="orb" style={{ width: 120, height: 120, background: "var(--blue)", left: -10, top: -10, opacity: 0.15 }} />
            <div className="orb" style={{ width: 80, height: 80, background: "var(--teal)", left: 20, top: 20, opacity: 0.12, animationDelay: "2s" }} />
            <div
              className="relative w-24 h-24 rounded-full flex items-center justify-center text-4xl font-bold z-10"
              style={{ background: "linear-gradient(135deg, rgba(14,138,240,.2), rgba(0,201,167,.15))", border: "2px solid rgba(14,138,240,.3)" }}
            >
              S
            </div>
          </div>

          <div className="text-center space-y-2">
            <h1 className="text-3xl font-bold gradient-text">Samantha</h1>
            <p style={{ color: "var(--muted)", fontSize: 15, maxWidth: 380 }}>
              Your local AI assistant — speaks, browses, automates. <br/>
              Everything runs on your machine.
            </p>
          </div>

          <div className="grid grid-cols-2 gap-2 w-full max-w-sm">
            {[
              "Open Spotify",
              "Search Wikipedia for AI",
              "Play lo-fi music on YouTube",
              "What can you do?",
            ].map((s) => (
              <button
                key={s}
                onClick={() => setText(s)}
                className="text-left px-3 py-2 rounded-lg text-sm transition-all hover:scale-[1.01]"
                style={{
                  background: "var(--card)",
                  border: "1px solid var(--border)",
                  color: "var(--muted)",
                }}
              >
                {s}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ── Message list ──────────────────────────────────────── */}
      {messages.length > 0 && (
        <div
          ref={scrollRef}
          className="flex-1 overflow-y-auto px-6 py-4 space-y-4"
          style={{ userSelect: "text", WebkitUserSelect: "text" } as React.CSSProperties}
        >
          {messages.map((m) => (
            <MessageBubble key={m.id} message={m} />
          ))}

          {/* Typing indicator */}
          {(agentState === "thinking" || agentState === "acting") && (
            <div className="flex gap-3 animate-fade-in">
              <div
                className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold"
                style={{ background: "linear-gradient(135deg, var(--purple), var(--pink))" }}
              >
                S
              </div>
              <div className="flex items-center gap-1 px-4 py-3 rounded-2xl rounded-tl-sm msg-assistant">
                <div className="flex gap-1">
                  {[0, 1, 2].map((i) => (
                    <div
                      key={i}
                      className="w-1.5 h-1.5 rounded-full"
                      style={{
                        background: "var(--muted)",
                        animation: `wave 1s ease-in-out ${i * 0.15}s infinite`,
                      }}
                    />
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ── Input area ────────────────────────────────────────── */}
      <div className="px-4 py-3 border-t" style={{ borderColor: "var(--border)" }}>
        <div className="flex items-end gap-3">
          {/* Voice button (STT managed by backend) */}
          {settings.sttMode !== "text" && (
            <VoiceButton />
          )}

          {/* Text input */}
          <div className="flex-1 relative">
            <textarea
              className="chat-input no-drag"
              placeholder={
                !connected ? "Start the backend to begin…" :
                isBusy     ? "Samantha is busy…" :
                "Type a message or speak your command…"
              }
              value={text}
              onChange={(e) => setText(e.target.value)}
              onKeyDown={handleKey}
              disabled={!connected || isBusy || sending}
              rows={1}
              style={{ maxHeight: 120, overflowY: text.split("\n").length > 3 ? "auto" : "hidden" }}
            />
          </div>

          {/* Send button */}
          <button
            className="btn-primary h-[44px] px-4 self-end no-drag"
            onClick={sendTextMessage}
            disabled={!text.trim() || !connected || isBusy || sending}
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  );
}
