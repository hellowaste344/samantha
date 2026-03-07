# ═══════════════════════════════════════════════════════════════════════════════
#  ZenonAI Samantha — unified Makefile
#
#  Three components, one architecture:
#    audio-engine/   Rust mic daemon  (samantha-audio binary)
#    agent/          Python AI agent  (FastAPI + Ollama + edge-tts)
#    desktop/        Tauri desktop    (React + Rust shell)
#
#  Connection flow:
#    Tauri desktop  →  invoke("start_backend")  →  spawns Python sidecar
#    Python agent   →  http://127.0.0.1:7799    →  REST + WebSocket
#    Tauri frontend →  ws://127.0.0.1:7799/ws/events  (state + transcript)
#    Tauri overlay  →  POST /api/chat           (typed messages)
#    Python agent   →  /tmp/samantha_audio.sock (Rust IPC, rust_bridge mode)
# ═══════════════════════════════════════════════════════════════════════════════

.PHONY: all build build-rust build-python build-desktop \
        run run-text run-voice run-daemon \
        install install-service \
        test-planner clean help

AUDIO_BIN  := audio-engine/target/release/samantha-audio
PYTHON      := python3
PIP         := pip3
AGENT_DIR   := agent

# ── Build ─────────────────────────────────────────────────────────────────────

all: build

build: build-rust build-python
	@echo ""
	@echo "✅  All components built."
	@echo "    Run:  make run-text    (no mic, no Rust — quickest start)"
	@echo "    Run:  make run-voice   (Python mic, no Rust)"
	@echo "    Run:  make run         (full: Rust mic engine + Python agent)"

build-rust:
	@echo "🦀  Building Rust audio engine…"
	@if ! command -v cargo > /dev/null 2>&1; then \
		echo ""; \
		echo "  ✗  cargo not found.  Install Rust first:"; \
		echo "     curl https://sh.rustup.rs -sSf | sh"; \
		echo "     source \$$HOME/.cargo/env"; \
		echo ""; \
		echo "  Arch Linux:    sudo pacman -S rust"; \
		echo "  Debian/Ubuntu: sudo apt install cargo"; \
		exit 1; \
	fi
	@echo "  cargo: $$(cargo --version)"
	@echo "  rustc: $$(rustc --version)"
	cd audio-engine && cargo build --release

build-python:
	@echo "🐍  Installing Python dependencies…"
	$(PIP) install --upgrade pip --quiet
	$(PIP) install -r $(AGENT_DIR)/requirements.txt --quiet
	@echo "✓  Python deps installed."

build-desktop:
	@echo "🖥  Building Tauri desktop…"
	@if ! command -v node > /dev/null 2>&1; then \
		echo "  ✗  node not found. Install Node.js >= 18 first."; exit 1; \
	fi
	@if ! command -v cargo > /dev/null 2>&1; then \
		echo "  ✗  cargo not found. Install Rust first."; exit 1; \
	fi
	cd desktop && npm install && npm run tauri:build

# ── Run ───────────────────────────────────────────────────────────────────────

run: build-rust
	@echo "🚀  Starting Samantha (Rust engine + Python agent)…"
	@echo "    Socket: /tmp/samantha_audio.sock"
	$(AUDIO_BIN) &
	sleep 1
	cd $(AGENT_DIR) && $(PYTHON) main.py

run-voice:
	@echo "🚀  Starting Samantha (Python voice, no Rust)…"
	cd $(AGENT_DIR) && STT_MODE=voice $(PYTHON) main.py --voice

run-text:
	@echo "🚀  Starting Samantha (text/keyboard mode — no mic)…"
	cd $(AGENT_DIR) && STT_MODE=text $(PYTHON) main.py --text

run-daemon:
	@echo "🚀  Starting Samantha daemon (headless, for Tauri sidecar)…"
	cd $(AGENT_DIR) && $(PYTHON) main.py --daemon

# ── Test ──────────────────────────────────────────────────────────────────────

test-planner:
	@echo "🧪  Smoke-testing Ollama planner…"
	cd $(AGENT_DIR) && $(PYTHON) main.py --test

# ── Install (systemd) ─────────────────────────────────────────────────────────

install: build-rust
	@echo "📦  Installing samantha-audio to /usr/local/bin…"
	sudo install -m 755 $(AUDIO_BIN) /usr/local/bin/samantha-audio
	@echo "✓  Audio engine installed."

install-service: install
	@echo "🔧  Installing systemd user service…"
	mkdir -p ~/.config/systemd/user
	cp packaging/samantha.service ~/.config/systemd/user/
	systemctl --user daemon-reload
	systemctl --user enable samantha-audio
	systemctl --user start  samantha-audio
	@echo "✓  samantha-audio service enabled and started."
	@echo "    Check status:  systemctl --user status samantha-audio"

# ── Clean ─────────────────────────────────────────────────────────────────────

clean:
	cd audio-engine && cargo clean
	rm -f $(AGENT_DIR)/memory.db
	@echo "✓  Cleaned."

# ── Help ──────────────────────────────────────────────────────────────────────

help:
	@echo ""
	@echo "  ZenonAI Samantha — Build System"
	@echo ""
	@echo "  make build          Build Rust audio engine + install Python deps"
	@echo "  make build-desktop  Build Tauri desktop app (needs Node + Rust)"
	@echo "  make run            Full run: Rust engine + Python agent"
	@echo "  make run-text       Quickstart: text input, no mic, no Rust"
	@echo "  make run-voice      Python mic (sounddevice), no Rust"
	@echo "  make run-daemon     Headless mode (Tauri sidecar)"
	@echo "  make test-planner   Smoke-test Ollama LLM planner"
	@echo "  make install        Install samantha-audio to /usr/local/bin"
	@echo "  make install-service Install + enable systemd service"
	@echo ""
