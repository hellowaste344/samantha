import type { Message } from "@/types";

interface Props {
  message: Message;
}

function formatTime(d: Date) {
  return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

export function MessageBubble({ message }: Props) {
  const { role, text, timestamp, actions } = message;

  if (role === "system") {
    return (
      <div className="flex justify-center animate-fade-in">
        <span
          className="text-xs px-3 py-1 rounded-full"
          style={{ color: "var(--muted)", background: "rgba(255,255,255,.03)", border: "1px solid var(--border)" }}
        >
          {text}
        </span>
      </div>
    );
  }

  const isUser = role === "user";

  return (
    <div
      className={`flex gap-3 animate-slide-up ${isUser ? "flex-row-reverse" : "flex-row"}`}
    >
      {/* Avatar */}
      <div
        className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold"
        style={{
          background: isUser
            ? "linear-gradient(135deg, var(--blue), var(--teal))"
            : "linear-gradient(135deg, var(--purple), var(--pink))",
        }}
      >
        {isUser ? "Y" : "S"}
      </div>

      {/* Bubble */}
      <div className={`flex flex-col gap-1 max-w-[75%] ${isUser ? "items-end" : "items-start"}`}>
        {/* Action tags */}
        {actions && actions.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {actions.map((a) => (
              <span
                key={a}
                className="text-xs px-2 py-0.5 rounded-full"
                style={{
                  background: "rgba(124,77,255,.1)",
                  border:     "1px solid rgba(124,77,255,.2)",
                  color:      "var(--purple)",
                }}
              >
                {a}
              </span>
            ))}
          </div>
        )}

        <div
          className={`px-4 py-3 rounded-2xl text-sm leading-relaxed ${isUser ? "msg-user rounded-tr-sm" : "msg-assistant rounded-tl-sm"}`}
          style={{ wordBreak: "break-word" }}
        >
          {text}
        </div>

        <span className="text-xs" style={{ color: "var(--muted)" }}>
          {formatTime(timestamp)}
        </span>
      </div>
    </div>
  );
}
