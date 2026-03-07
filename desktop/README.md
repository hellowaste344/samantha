# Samantha Desktop — Tauri + React

Cross-platform desktop app for Samantha AI by ZenonAI.

Built with **Tauri 2**, **React 18**, **TypeScript**, **Vite**, and **Tailwind CSS**.

---

## Features

- 💬 **Live chat interface** — real-time transcript of voice + text interactions
- 🎙 **Voice status display** — listening/thinking/acting/speaking indicators with animations
- ⚙️ **Settings panel** — model, voice, STT mode, theme — all saved locally
- 🕘 **Conversation history** — powered by SQLite memory from the Python backend
- 🔔 **System tray** — minimises to tray, shows/hides on click
- 🚀 **Backend management** — start/stop the Python sidecar from the UI
- 🌙 **Dark/light theme** — persists across sessions
- 🔑 **No cloud, no keys** — everything talks to `localhost:7799`

---

## Prerequisites

- [Node.js 18+](https://nodejs.org)
- [Rust toolchain](https://rustup.rs)
- [Tauri CLI v2](https://tauri.app): `cargo install tauri-cli --version "^2.0"`
- The Samantha Python backend (see `../zenonai_v2/install/`)

---

## Development

```bash
# Install dependencies
npm install

# Start dev server + Tauri window
npm run tauri:dev
```

The app connects to the backend at `ws://127.0.0.1:7799/ws/events`.
Start the backend separately:

```bash
cd ../zenonai_v2/agent
source .venv/bin/activate
python main.py --daemon
```

---

## Production Build

```bash
npm run tauri:build
```

Outputs platform-native bundles in `src-tauri/target/release/bundle/`:

| Platform | Format |
|----------|--------|
| macOS | `.dmg`, `.app` |
| Windows | `.exe` (NSIS installer) |
| Linux | `.deb`, `.AppImage`, `.rpm` |

For a fully bundled release (with PyInstaller backend sidecar), use:
```bash
../zenonai_v2/packaging/build.sh
```

---

## Project Structure

```
zenonai_desktop/
├── src/
│   ├── components/
│   │   ├── TitleBar.tsx       — Custom window titlebar + controls
│   │   ├── Sidebar.tsx        — Icon nav + backend power toggle
│   │   ├── ChatView.tsx       — Main conversation interface
│   │   ├── MessageBubble.tsx  — User/assistant/system messages
│   │   ├── StatusBar.tsx      — Connection + agent state
│   │   ├── VoiceButton.tsx    — Animated mic button
│   │   ├── HistoryPanel.tsx   — Past conversations
│   │   └── SettingsPanel.tsx  — All configuration
│   ├── hooks/
│   │   ├── useWebSocket.ts    — WS connection with auto-reconnect
│   │   └── useAgent.ts        — Backend control via Tauri invoke
│   ├── store/
│   │   └── agentStore.ts      — Zustand state (agent + settings)
│   └── types/
│       └── index.ts           — Shared TypeScript interfaces
│
└── src-tauri/
    ├── src/lib.rs             — Tauri commands, tray, sidecar launch
    └── tauri.conf.json        — App config, bundle settings
```

---

## Environment

No `.env` file needed for the frontend — all config is in the Settings panel, persisted via Zustand's `persist` middleware (stored in `localStorage`).

The Tauri Rust side uses no secrets.

---

© 2025 ZenonAI · [zenonai.net](https://zenonai.net)
