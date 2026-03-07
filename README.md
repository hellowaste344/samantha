# ZenonAI — Samantha

Local AI voice assistant. Runs 100% on your machine — no cloud, no subscriptions.

## Directory structure

```
zenonai/
├── desktop/          Tauri desktop app (React + Rust shell)
│   ├── src/          React components, hooks, store, types
│   └── src-tauri/    Tauri Rust shell (windows, tray, backend spawn)
│
├── agent/            Python AI backend
│   ├── api/          FastAPI server (REST + WebSocket bridge)
│   ├── core/         Orchestrator, Planner (Ollama), Memory, Context
│   ├── voice_io/     STT (faster-whisper), TTS (edge-tts), AudioBridge
│   └── tools/        Browser, Gmail, Wikipedia, OS control
│
├── audio-engine/     Rust mic daemon
│   └── src/          cpal capture, WebRTC VAD, Unix socket IPC
│
└── packaging/        systemd service file
```

## Architecture — how the pieces connect

```
Tauri desktop (desktop/)
  │  invoke("start_backend")    →  spawns Python sidecar
  │  GET  /health               →  liveness probe
  │  GET  /api/status           →  model + engine info
  │  GET  /api/history          →  SQLite conversation history
  │  POST /api/chat {text}      →  typed message → agent
  │  WS   /ws/events            →  real-time state + transcript
  ▼
Python agent (agent/)  ←→  localhost:7799
  │  FastAPI server
  │  Orchestrator (conversation loop)
  │  Planner     (Ollama deepseek-r1:7b)
  │  TTS         (edge-tts neural voices)
  │  STT         (faster-whisper)
  │    ↑ typed messages via _pump_chat_queue()
  │    ↑ voice via AudioBridge (rust_bridge mode)
  ▼
Rust audio daemon (audio-engine/)  ←  /tmp/samantha_audio.sock
  cpal mic capture → WebRTC VAD → Unix socket IPC
```

## Quick start (no Tauri build needed)

```bash
# 1. Prerequisites
ollama serve &
ollama pull deepseek-r1:7b

# 2. Install Python deps
pip install -r agent/requirements.txt

# 3. Configure
cp agent/.env.example agent/.env
# edit agent/.env if needed

# 4. Run in text mode (no mic, no Rust required)
make run-text

# — or — Python mic mode
make run-voice

# — or — Full mode with Rust audio engine
make build-rust && make run
```

## Building the Tauri desktop

```bash
# Prerequisites: Node.js >= 18, Rust, system libs
# Linux: sudo apt install libwebkit2gtk-4.1-dev libgtk-3-dev
#   or   sudo pacman -S webkit2gtk-4.1 gtk3

cd desktop
npm install
npm run tauri:dev      # development
npm run tauri:build    # production build
```

The Tauri app bundles the Python backend as a **sidecar** binary.
Click **Start Agent** in the overlay bar or settings to launch it.

## Environment variables (agent/.env)

| Variable | Default | Description |
|----------|---------|-------------|
| `OLLAMA_MODEL` | `deepseek-r1:7b` | LLM model |
| `STT_MODE` | `rust_bridge` | `rust_bridge` / `voice` / `text` |
| `TTS_ENGINE` | `edge` | `edge` / `piper` / `pyttsx3` / `none` |
| `TTS_EDGE_VOICE` | `aria` | aria / jenny / guy / ryan / sonia … |
| `API_PORT` | `7799` | REST + WebSocket port |
| `WHISPER_MODEL` | `small` | tiny / base / small / medium / large-v3 |
