import { useEffect, useState } from "react";
import { listen } from "@tauri-apps/api/event";
import { TitleBar }      from "@/components/TitleBar";
import { Sidebar }       from "@/components/Sidebar";
import { ChatView }      from "@/components/ChatView";
import { HistoryPanel }  from "@/components/HistoryPanel";
import { SettingsPanel } from "@/components/SettingsPanel";
import { StatusBar }     from "@/components/StatusBar";
import { LaunchPopup }   from "@/components/LaunchPopup";
import { OverlayBar }    from "@/components/OverlayBar";
import { useAgentStore, useSettingsStore } from "@/store/agentStore";
import { useWebSocket }  from "@/hooks/useWebSocket";
import { useAgent }      from "@/hooks/useAgent";

// ── Resolve which window this is ──────────────────────────────────────────────
// We read the label asynchronously so a crash in the Tauri API never blank-screens the app.
// While resolving we show nothing (instant, <1 frame), then render the right UI.
// Fallback: if not inside Tauri at all (e.g. plain browser dev), show the launch popup.

type WindowLabel = "launch" | "overlay" | "main";

function getWindowLabel(): Promise<WindowLabel> {
  return import("@tauri-apps/api/window")
    .then(m => m.getCurrentWindow().label as WindowLabel)
    .catch(() => "launch"); // fallback for plain browser / build preview
}

export default function App() {
  const [windowLabel, setWindowLabel] = useState<WindowLabel | null>(null);

  const { activeView, setActiveView } = useAgentStore();
  const { settings }                  = useSettingsStore();
  const { checkBackendHealth }        = useAgent();
  useWebSocket();

  // Resolve window label on mount
  useEffect(() => {
    getWindowLabel().then(setWindowLabel);
  }, []);

  // Apply theme
  useEffect(() => {
    document.documentElement.setAttribute("data-theme", settings.theme);
  }, [settings.theme]);

  // Ping backend (main window only)
  useEffect(() => {
    if (windowLabel === "main") checkBackendHealth();
  }, [windowLabel]); // eslint-disable-line

  // Listen for cross-window navigate events
  useEffect(() => {
    if (windowLabel !== "main") return;
    const unlisten = listen<string>("navigate", (e) => {
      if (e.payload === "settings") setActiveView("settings");
    });
    return () => { unlisten.then(f => f()); };
  }, [windowLabel, setActiveView]);

  // While resolving the window label, render nothing (avoids flash)
  if (windowLabel === null) return null;

  // ── Route to the correct UI for this window ───────────────────────────────
  if (windowLabel === "overlay") return <OverlayBar />;
  if (windowLabel === "launch")  return <LaunchPopup />;

  // ── Main window ────────────────────────────────────────────────────────────
  return (
    <div
      className="flex flex-col h-screen overflow-hidden"
      style={{ background: "var(--bg)", color: "var(--text)" }}
    >
      <TitleBar />
      <div className="flex flex-1 overflow-hidden">
        <Sidebar />
        <main className="flex-1 flex flex-col overflow-hidden">
          {activeView === "chat"     && <ChatView />}
          {activeView === "history"  && <HistoryPanel />}
          {activeView === "settings" && <SettingsPanel />}
        </main>
      </div>
      <StatusBar />
    </div>
  );
}
