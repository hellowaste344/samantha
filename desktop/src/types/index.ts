// ─── Agent state types ─────────────────────────────────────────────────────────

export type AgentState =
  | "disconnected"
  | "connecting"
  | "idle"
  | "listening"
  | "thinking"
  | "acting"
  | "speaking";

export interface AgentStatus {
  state:      AgentState;
  actions?:   string[];
  agent?:     string;
  stt_mode?:  string;
  tts_engine?:string;
  llm_model?: string;
  uptime?:    number;
}

// ─── Message / transcript ──────────────────────────────────────────────────────

export type MessageRole = "user" | "assistant" | "system";

export interface Message {
  id:        string;
  role:      MessageRole;
  text:      string;
  timestamp: Date;
  actions?:  string[];
}

// ─── Memory / history ─────────────────────────────────────────────────────────

export interface MemoryTurn {
  ts:    string;
  user:  string;
  agent: string;
}

export interface HistoryResponse {
  turns: MemoryTurn[];
  total: number;
}

// ─── WebSocket events ─────────────────────────────────────────────────────────

export interface WsTranscriptEvent {
  type:  "transcript";
  role:  "user" | "assistant";
  text:  string;
}

export interface WsStatusEvent {
  type:    "status";
  state:   AgentState;
  actions?: string[];
}

export type WsEvent = WsTranscriptEvent | WsStatusEvent;

// ─── Settings ─────────────────────────────────────────────────────────────────

export interface AppSettings {
  apiPort:               number;
  sttMode:               "rust_bridge" | "voice" | "text";
  ollamaModel:           string;
  ttsVoice:              string;
  ttsEngine:             "edge" | "piper" | "pyttsx3" | "none";
  theme:                 "dark" | "light";
  autostart:             boolean;
  windowOpacity:         number;
  // Vision / automation
  nvidiaCaptureEnabled:  boolean;  // NVFBC/PyNvCodec if true, mss if false
  visionEnabled:         boolean;  // YOLOv9 + Tesseract on/off
  yoloModel:             "yolov9n" | "yolov9s" | "yolov8n" | "yolov8s";
  actionBackend:         "pynput" | "xdotool";
}

export const DEFAULT_SETTINGS: AppSettings = {
  apiPort:               7799,
  sttMode:               "rust_bridge",
  ollamaModel:           "deepseek-r1:7b",
  ttsVoice:              "aria",
  ttsEngine:             "edge",
  theme:                 "dark",
  autostart:             false,
  windowOpacity:         1,
  nvidiaCaptureEnabled:  false,
  visionEnabled:         false,
  yoloModel:             "yolov9n",
  actionBackend:         "pynput",
};

// ─── Models list ──────────────────────────────────────────────────────────────

export interface OllamaModel {
  name:    string;
  tag:     string;
  size:    string;
  pull:    string;
  env:     string;
}

export const OLLAMA_MODELS: OllamaModel[] = [
  { name: "deepseek-r1:7b", tag: "Recommended", size: "~4 GB", pull: "deepseek-r1:7b", env: "deepseek-r1:7b" },
  { name: "Mistral 7B",     tag: "Mistral",     size: "~4 GB", pull: "mistral",         env: "mistral"        },
  { name: "LLaMA 3 8B",     tag: "Meta",        size: "~5 GB", pull: "llama3",          env: "llama3"         },
  { name: "Phi-3 Mini",     tag: "Microsoft",   size: "~2 GB", pull: "phi3",            env: "phi3"           },
  { name: "Gemma 2 9B",     tag: "Google",      size: "~5 GB", pull: "gemma2",          env: "gemma2"         },
  { name: "Neural Chat",    tag: "Intel",       size: "~4 GB", pull: "neural-chat",     env: "neuralchat"     },
];

export const TTS_VOICES = [
  { key: "aria",    name: "Aria",    gender: "Female", locale: "en-US" },
  { key: "jenny",   name: "Jenny",   gender: "Female", locale: "en-US" },
  { key: "guy",     name: "Guy",     gender: "Male",   locale: "en-US" },
  { key: "davis",   name: "Davis",   gender: "Male",   locale: "en-US" },
  { key: "ryan",    name: "Ryan",    gender: "Male",   locale: "en-GB" },
  { key: "sonia",   name: "Sonia",   gender: "Female", locale: "en-GB" },
  { key: "natasha", name: "Natasha", gender: "Female", locale: "en-AU" },
  { key: "william", name: "William", gender: "Male",   locale: "en-AU" },
];
