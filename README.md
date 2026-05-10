# Samantha — ZenonAI

```
Mic ──► [Rust: cpal + WebRTC VAD]
                 │  unix socket
                 ▼
        [faster-whisper STT]
                 │  transcript
                 ▼
        [Ollama LLM planner] ──► JSON action plan
                 │
        ┌────────┼──────────────┐
        ▼        ▼              ▼
    Browser  OS Control   Screen Vision
   Playwright PyAutoGUI  MSS+YOLOv8+OCR
                 │
                 ▼  WebSocket :7799
        [Tauri desktop UI]
                 │
                 ▼
          [edge-tts] ──► Speaker
```

---

## Commands

```bash
make install    # install all deps — run once
make backend    # start the AI agent (voice + LLM + API)
make platform   # start the desktop UI (Tauri)
make run        # start both together
make clean      # remove build artefacts
```

Configure once before first run:
```bash
cp agent/.env.example agent/.env
```

---

## Stack

| Layer | Tech |
|---|---|
| Voice capture | Rust · cpal · WebRTC VAD |
| Speech-to-text | faster-whisper (tiny → large-v3) |
| LLM | Ollama · llama3.2:3b |
| Browser | Playwright · Chromium |
| Screen vision | MSS · OpenCV · YOLOv8 · PaddleOCR |
| Text-to-speech | edge-tts (neural, 300+ voices) |
| Desktop UI | Tauri v2 · React · TypeScript |
| API | FastAPI · WebSocket |

---

## Config (`agent/.env`)

```dotenv
OLLAMA_MODEL=llama3.2:3b
WHISPER_MODEL=tiny
STT_MODE=rust_bridge        # rust_bridge | voice | text
TTS_EDGE_VOICE=aria
HF_TOKEN=hf_your_token_here
```

~SAMANTHA
samantha is an open source voice interactive AI agent lives on your machine, runs offline built on top of LLM to simplify human interactions with computers and help agents gain more control on your desktop for instance; environment perception via webcam, app interaction, or browser navigation.  Sounds lunatic! yes but in fact it is possible!
