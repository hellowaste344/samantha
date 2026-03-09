# ══════════════════════════════════════════════════════════════════════════════
#  Samantha — ZenonAI
#
#  Components
#    audio-engine/   Rust mic daemon   (samantha-audio)
#    agent/          Python AI backend (Ollama + Whisper + FastAPI)
#    desktop/        Tauri frontend    (React + Rust shell)
#
#  Flow — Linux / macOS
#    mic → [samantha-audio: cpal+VAD] → unix socket → [agent] → [Ollama LLM]
#
#  Flow — WSL (Windows mic is invisible to Linux kernel)
#    mic → [windows_mic_bridge.py on Windows: WASAPI+VAD] → TCP → [agent]
# ══════════════════════════════════════════════════════════════════════════════

ROOT        := $(shell pwd)
AGENT_DIR   := $(ROOT)/agent
AUDIO_DIR   := $(ROOT)/audio-engine
DESKTOP_DIR := $(ROOT)/desktop
VENV        := $(AGENT_DIR)/.venv
PYTHON      := $(VENV)/bin/python
PIP         := $(VENV)/bin/pip
AUDIO_BIN   := $(AUDIO_DIR)/target/release/samantha-audio

CARGO_BIN   := $(HOME)/.cargo/bin/cargo
CARGO       := $(shell command -v cargo 2>/dev/null || echo $(CARGO_BIN))

PYTHON3     := $(shell \
  for c in python3.13 python3.12 python3.11 python3; do \
    b=$$(command -v $$c 2>/dev/null); \
    if [ -n "$$b" ] && $$b -c "import sys; exit(0 if sys.version_info>=(3,11) else 1)" 2>/dev/null; \
    then echo $$b; break; fi; done)

# ── OLLAMA_MODEL — read dynamically from .env, fall back to .env.example ──────
# Read straight from the .env file with shell grep so it works before the
# venv exists and without any Python import tricks.
OLLAMA_MODEL := $(shell \
  grep -E "^OLLAMA_MODEL=" $(AGENT_DIR)/.env 2>/dev/null \
  | cut -d= -f2 | tr -d ' \r')
OLLAMA_MODEL := $(or $(OLLAMA_MODEL),$(shell \
  grep -E "^OLLAMA_MODEL=" $(AGENT_DIR)/.env.example 2>/dev/null \
  | cut -d= -f2 | tr -d ' \r'))
OLLAMA_MODEL := $(or $(OLLAMA_MODEL),mistral)

# ── Environment detection ─────────────────────────────────────────────────────
# IS_WSL MUST be checked before OS_TYPE — WSL reports uname -s as "Linux" so
# if OS_TYPE were tested first the WSL branch in _sys would never be reached.

IS_WSL  := $(shell grep -qiE "microsoft|WSL" /proc/version 2>/dev/null \
                   && echo true || echo false)
UNAME   := $(shell uname -s)
ifeq ($(UNAME), Darwin)
  OS_TYPE := macos
else
  OS_TYPE := linux
endif

# ── Audio transport ───────────────────────────────────────────────────────────
AUDIO_TCP_PORT := 9876

ifeq ($(IS_WSL), true)
  AUDIO_SOCKET := tcp://127.0.0.1:$(AUDIO_TCP_PORT)
else
  AUDIO_SOCKET := /tmp/samantha_audio.sock
endif

BOLD   := \033[1m
GREEN  := \033[0;32m
CYAN   := \033[0;36m
YELLOW := \033[0;33m
RED    := \033[0;31m
RESET  := \033[0m

.DEFAULT_GOAL := help
.PHONY: help install run backend platform clean \
        _sys _cargo _venv _pypackages _audio _ollama _node _env

# ══════════════════════════════════════════════════════════════════════════════
#  HELP
# ══════════════════════════════════════════════════════════════════════════════
help:
	@echo ""
	@echo "$(BOLD)  Samantha — ZenonAI$(RESET)"
	@echo ""
	@echo "  make install      Install all dependencies (Rust, Python, Node, Ollama)"
	@echo "  make backend      Run the AI agent  (voice + LLM + API server)"
	@echo "  make platform     Run the desktop UI (Tauri dev mode)"
	@echo "  make run          Run backend + platform together"
	@echo "  make clean        Remove build artefacts and venv"
	@echo ""
ifeq ($(IS_WSL), true)
	@echo "  $(YELLOW)WSL detected — audio bridge starts automatically$(RESET)"
	@echo "  Requires Windows Python: pip install sounddevice webrtcvad numpy"
	@echo ""
endif

# ══════════════════════════════════════════════════════════════════════════════
#  INSTALL
# ══════════════════════════════════════════════════════════════════════════════
install: _sys _cargo _venv _pypackages _audio _ollama _node
	@echo ""
	@echo "$(GREEN)$(BOLD)  ✓ Install complete$(RESET)"
	@echo ""
ifeq ($(IS_WSL), true)
	@echo "  $(YELLOW)WSL: install deps on Windows Python:$(RESET)"
	@echo "    pip install sounddevice webrtcvad numpy"
	@echo "  (mic bridge starts automatically via make backend)"
	@echo ""
endif
	@echo "  cp agent/.env.example agent/.env   # configure once"
	@echo "  make run"
	@echo ""

# ── System packages ───────────────────────────────────────────────────────────
# IS_WSL is checked first — if it were after the linux block, WSL would always
# match linux (since uname -s returns "Linux" on WSL) and skip the WSL branch.
_sys:
	@echo "$(CYAN)▶ System packages…$(RESET)"
ifeq ($(IS_WSL), true)
	@# WSL: no ALSA/PortAudio — mic capture runs on the Windows side
	@sudo apt-get update -qq && sudo apt-get install -y \
		build-essential pkg-config git curl \
		python3-venv python3-pip python3-dev \
		ffmpeg tesseract-ocr tesseract-ocr-eng scrot python3-tk 2>/dev/null || true
else ifeq ($(OS_TYPE), macos)
	@brew install pkg-config ffmpeg tesseract python@3.11 || true
else
	@if command -v pacman >/dev/null 2>&1; then \
		sudo pacman -Sy --needed --noconfirm \
			base-devel pkgconf git curl python \
			alsa-lib portaudio ffmpeg tesseract tesseract-data-eng scrot tk; \
	elif command -v apt-get >/dev/null 2>&1; then \
		sudo apt-get update -qq && sudo apt-get install -y \
			build-essential pkg-config git curl \
			python3-venv python3-pip python3-dev \
			libasound2-dev portaudio19-dev ffmpeg \
			tesseract-ocr tesseract-ocr-eng scrot python3-tk; \
	fi
endif
	@echo "$(GREEN)  ✓ System packages$(RESET)"

_cargo:
	@if command -v cargo >/dev/null 2>&1 || [ -x "$(CARGO_BIN)" ]; then \
		echo "$(GREEN)  ✓ Rust already installed$(RESET)"; \
	else \
		echo "$(CYAN)▶ Installing Rust…$(RESET)"; \
		curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path; \
		echo "$(GREEN)  ✓ Rust installed$(RESET)"; \
	fi

_venv:
	@if [ -z "$(PYTHON3)" ]; then \
		echo "$(RED)  ✗ Python 3.11+ not found. Install it then re-run make install.$(RESET)"; exit 1; \
	fi
	@if [ ! -d "$(VENV)" ]; then \
		echo "$(CYAN)▶ Creating Python venv…$(RESET)"; \
		$(PYTHON3) -m venv $(VENV); \
		echo "$(GREEN)  ✓ venv at agent/.venv$(RESET)"; \
	else \
		echo "$(GREEN)  ✓ venv exists$(RESET)"; \
	fi

_pypackages: _venv
	@echo "$(CYAN)▶ Python packages…$(RESET)"
	@$(PIP) install --upgrade pip setuptools wheel -q
	@$(PIP) install -r $(AGENT_DIR)/requirements.txt
	@$(PIP) install paddlepaddle paddleocr 2>/dev/null \
		&& echo "$(GREEN)  ✓ PaddleOCR$(RESET)" \
		|| echo "$(YELLOW)  ⚠  PaddleOCR unavailable — Tesseract fallback active$(RESET)"
	@$(PYTHON) -m playwright install chromium
	@echo "$(GREEN)  ✓ Python packages$(RESET)"

_audio: _cargo
ifeq ($(IS_WSL), true)
	@echo "$(YELLOW)  ⚠  WSL: skipping Rust audio engine (mic runs on Windows)$(RESET)"
else
	@echo "$(CYAN)▶ Building audio engine…$(RESET)"
	@cd $(AUDIO_DIR) && $(CARGO) build --release
	@echo "$(GREEN)  ✓ samantha-audio built$(RESET)"
endif

# ── Ollama ────────────────────────────────────────────────────────────────────
_ollama:
	@if command -v ollama >/dev/null 2>&1; then \
		echo "$(GREEN)  ✓ Ollama already installed$(RESET)"; \
	else \
		echo "$(CYAN)▶ Installing Ollama…$(RESET)"; \
		curl -fsSL https://ollama.com/install.sh | sh; \
	fi
	@if ollama list 2>/dev/null | grep -q "$(OLLAMA_MODEL)"; then \
		echo "$(GREEN)  ✓ $(OLLAMA_MODEL) present$(RESET)"; \
	else \
		echo "$(CYAN)▶ Pulling $(OLLAMA_MODEL)…$(RESET)"; \
		ollama pull $(OLLAMA_MODEL); \
	fi

_node:
	@if ! command -v node >/dev/null 2>&1; then \
		echo "$(YELLOW)  ⚠  Node.js not found — desktop UI won't build.$(RESET)"; \
		echo "     Install: https://nodejs.org  (v18+)"; \
	else \
		echo "$(GREEN)  ✓ Node $$(node --version) found$(RESET)"; \
		echo "$(CYAN)▶ npm install (desktop)…$(RESET)"; \
		cd $(DESKTOP_DIR) && npm install --silent; \
		echo "$(GREEN)  ✓ desktop deps$(RESET)"; \
	fi

_env:
	@if [ ! -f "$(AGENT_DIR)/.env" ]; then \
		cp $(AGENT_DIR)/.env.example $(AGENT_DIR)/.env; \
		echo "$(YELLOW)  ⚠  Created agent/.env from example — edit before running$(RESET)"; \
	fi
	@if grep -q "^AUDIO_SOCKET=" $(AGENT_DIR)/.env; then \
		sed -i'' -e "s|^AUDIO_SOCKET=.*|AUDIO_SOCKET=$(AUDIO_SOCKET)|" $(AGENT_DIR)/.env; \
	else \
		echo "AUDIO_SOCKET=$(AUDIO_SOCKET)" >> $(AGENT_DIR)/.env; \
	fi

# ══════════════════════════════════════════════════════════════════════════════
#  BACKEND  (audio daemon + Python agent)
# ══════════════════════════════════════════════════════════════════════════════
backend: _env
	@echo "$(CYAN)▶ Starting backend…$(RESET)"
ifeq ($(IS_WSL), true)
	@WIN_PY=$$(command -v python.exe 2>/dev/null); \
	if [ -z "$$WIN_PY" ]; then \
		echo "$(RED)  ✗ python.exe not found.$(RESET)"; \
		echo "    Install Python on Windows, tick 'Add to PATH', then:"; \
		echo "    pip install sounddevice webrtcvad numpy"; \
		exit 1; \
	fi; \
	BRIDGE_WIN=$$(wslpath -w $(AGENT_DIR)/voice_io/windows_mic_bridge.py); \
	if ! netstat -tn 2>/dev/null | grep -q ":$(AUDIO_TCP_PORT).*LISTEN"; then \
		$$WIN_PY "$$BRIDGE_WIN" $(AUDIO_TCP_PORT) >/tmp/windows_mic_bridge.log 2>&1 & \
		sleep 1; \
		echo "$(GREEN)  ✓ windows_mic_bridge started (port $(AUDIO_TCP_PORT))$(RESET)"; \
	else \
		echo "$(GREEN)  ✓ windows_mic_bridge already running$(RESET)"; \
	fi
else
	@if [ -f "$(AUDIO_BIN)" ]; then \
		if ! pgrep -x samantha-audio >/dev/null 2>&1; then \
			$(AUDIO_BIN) --socket $(AUDIO_SOCKET) --sample-rate 16000 \
				>/tmp/samantha-audio.log 2>&1 & \
			sleep 1; \
			echo "$(GREEN)  ✓ samantha-audio started$(RESET)"; \
		else \
			echo "$(GREEN)  ✓ samantha-audio already running$(RESET)"; \
		fi; \
	else \
		echo "$(YELLOW)  ⚠  Audio engine not built — run make install first$(RESET)"; \
	fi
endif
	@cd $(AGENT_DIR) && $(PYTHON) main.py

# ══════════════════════════════════════════════════════════════════════════════
#  PLATFORM  (Tauri desktop — dev mode)
# ══════════════════════════════════════════════════════════════════════════════
platform:
	@echo "$(CYAN)▶ Starting desktop UI (Tauri dev)…$(RESET)"
	@if ! command -v node >/dev/null 2>&1; then \
		echo "$(RED)  ✗ Node.js not found. Install v18+ from nodejs.org$(RESET)"; exit 1; \
	fi
	@cd $(DESKTOP_DIR) && npm run tauri:dev

# ══════════════════════════════════════════════════════════════════════════════
#  RUN  (backend + platform in parallel)
# ══════════════════════════════════════════════════════════════════════════════
run: _env
	@$(MAKE) --no-print-directory backend & BACKEND_PID=$$!; \
	sleep 2; \
	trap "kill $$BACKEND_PID 2>/dev/null; wait $$BACKEND_PID 2>/dev/null" EXIT INT TERM; \
	$(MAKE) --no-print-directory platform; \
	kill $$BACKEND_PID 2>/dev/null; wait $$BACKEND_PID 2>/dev/null

# ══════════════════════════════════════════════════════════════════════════════
#  CLEAN
# ══════════════════════════════════════════════════════════════════════════════
clean:
	@echo "$(CYAN)▶ Cleaning…$(RESET)"
	@cd $(AUDIO_DIR) && $(CARGO) clean 2>/dev/null || true
	@rm -rf $(VENV)
	@rm -rf $(DESKTOP_DIR)/node_modules $(DESKTOP_DIR)/dist
	@rm -f $(AGENT_DIR)/memory.db /tmp/samantha-audio.log /tmp/windows_mic_bridge.log
	@echo "$(GREEN)  ✓ Clean$(RESET)"
