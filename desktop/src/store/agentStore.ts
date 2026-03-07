import { create } from "zustand";
import { persist } from "zustand/middleware";
import type {
  AgentState,
  AgentStatus,
  AppSettings,
  Message,
  MemoryTurn,
} from "@/types";
import { DEFAULT_SETTINGS } from "@/types";

// ─── Agent store ──────────────────────────────────────────────────────────────

interface AgentStore {
  // Connection
  connected:    boolean;
  connecting:   boolean;
  setConnected: (v: boolean) => void;
  setConnecting:(v: boolean) => void;

  // State
  agentState:   AgentState;
  agentStatus:  AgentStatus | null;
  setAgentState:(s: AgentState) => void;
  setAgentStatus:(s: AgentStatus) => void;

  // Messages
  messages:     Message[];
  addMessage:   (m: Omit<Message, "id" | "timestamp">) => void;
  clearMessages:() => void;

  // History
  history:      MemoryTurn[];
  setHistory:   (h: MemoryTurn[]) => void;

  // Active view
  activeView:   "chat" | "history" | "settings";
  setActiveView:(v: "chat" | "history" | "settings") => void;

  // Backend status
  backendRunning: boolean;
  setBackendRunning: (v: boolean) => void;
}

export const useAgentStore = create<AgentStore>()((set) => ({
  connected:    false,
  connecting:   false,
  setConnected: (v) => set({ connected: v }),
  setConnecting:(v) => set({ connecting: v }),

  agentState:    "disconnected",
  agentStatus:   null,
  setAgentState: (s) => set({ agentState: s }),
  setAgentStatus:(s) => set({ agentStatus: s, agentState: s.state }),

  messages:      [],
  addMessage: (m) =>
    set((state) => ({
      messages: [
        ...state.messages,
        { ...m, id: crypto.randomUUID(), timestamp: new Date() },
      ].slice(-200), // cap at 200 messages
    })),
  clearMessages: () => set({ messages: [] }),

  history:    [],
  setHistory: (h) => set({ history: h }),

  activeView:    "chat",
  setActiveView: (v) => set({ activeView: v }),

  backendRunning:    false,
  setBackendRunning: (v) => set({ backendRunning: v }),
}));

// ─── Settings store (persisted) ───────────────────────────────────────────────

interface SettingsStore {
  settings:     AppSettings;
  updateSettings:(patch: Partial<AppSettings>) => void;
  resetSettings: () => void;
}

export const useSettingsStore = create<SettingsStore>()(
  persist(
    (set) => ({
      settings: DEFAULT_SETTINGS,
      updateSettings: (patch) =>
        set((state) => ({ settings: { ...state.settings, ...patch } })),
      resetSettings: () => set({ settings: DEFAULT_SETTINGS }),
    }),
    { name: "zenon-settings" }
  )
);
