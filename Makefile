# ══════════════════════════════════════════════════════════════════════════════
#  Samantha — ZenonAI
#
#  Components
#    audio-engine/   Rust mic daemon   (samantha-audio)
#    agent/          Python AI backend (Ollama + Whisper + FastAPI)
#    desktop/        Tauri frontend    (React + Rust shell)
#
#  Flow
#    mic → [Rust VAD] → unix socket → [Python agent] → [Ollama LLM]
#                                            ↕ WebSocket :7799
#                                     [Tauri desktop]
# ══════════════════════════════════════════════════════════════════════════════

ROOT        := $(shell pwd)
AGENT_DIR   := $(ROOT)/agent
AUDIO_DIR   := $(ROOT)/audio-engine
DESKTOP_DIR := $(ROOT)/desktop
VENV        := $(AGENT_DIR)/.venv
PYTHON      := $(VENV)/bin/python
PIP         := $(VENV)/bin/pip
AUDIO_BIN   := $(AUDIO_DIR)/target/release/samantha-audio
SOCKET      := /tmp/samantha_audio.sock

CARGO_BIN   := $(HOME)/.cargo/bin/cargo
CARGO       := $(shell command -v cargo 2>/dev/null || echo $(CARGO_BIN))

PYTHON3     := $(shell \
  for c in python3.13 python3.12 python3.11 python3; do \
    b=$$(command -v $$c 2>/dev/null); \
    if [ -n "$$b" ] && $$b -c "import sys; exit(0 if sys.version_info>=(3,11) else 1)" 2>/dev/null; \
    then echo $$b; break; fi; done)

UNAME := $(shell uname -s)
ifeq ($(UNAME), Darwin)
  OS_TYPE := macos
else
  OS_TYPE := linux
endif

BOLD   := \033[1m
GREEN  := \033[0;32m
CYAN   := \033[0;36m
YELLOW := \033[0;33m
RESET  := \033[0m

.DEFAULT_GOAL := help
.PHONY: help install run backend platform clean \
        _venv _audio _ollama _env

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

# ══════════════════════════════════════════════════════════════════════════════
#  INSTALL
# ══════════════════════════════════════════════════════════════════════════════
install: _sys _cargo _venv _pypackages _audio _ollama _node
	@echo ""
	@echo "$(GREEN)$(BOLD)  ✓ Install complete$(RESET)"
	@echo ""
	@echo "  cp agent/.env.example agent/.env   # configure once"
	@echo "  make backend                        # start agent"
	@echo "  make platform                       # start desktop UI"
	@echo "  make run                            # start both"
	@echo ""

_sys:
	@echo "$(CYAN)▶ System packages…$(RESET)"
ifeq ($(OS_TYPE), linux)
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
else
	@brew install pkg-config ffmpeg tesseract python@3.11 || true
endif
	@echo "$(GREEN)  ✓ System packages$(RESET)"

_cargo:
	@if command -v cargo >/dev/null 2>&1 || [ -x "$(CARGO_BIN)" ]; then \
		echo "$(GREEN)  ✓ Rust $(shell rustc --version 2>/dev/null | cut -d' ' -f2) already installed$(RESET)"; \
	else \
		echo "$(CYAN)▶ Installing Rust…$(RESET)"; \
		curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --no-modify-path; \
		echo "$(GREEN)  ✓ Rust installed$(RESET)"; \
	fi

_venv:
	@if [ -z "$(PYTHON3)" ]; then \
		echo "$(YELLOW)  ✗ Python 3.11+ not found. Install it then re-run make install.$(RESET)"; exit 1; \
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
	@echo "$(CYAN)▶ Building audio engine…$(RESET)"
	@cd $(AUDIO_DIR) && $(CARGO) build --release
	@echo "$(GREEN)  ✓ samantha-audio built$(RESET)"

_ollama:
	@if command -v ollama >/dev/null 2>&1; then \
		echo "$(GREEN)  ✓ Ollama already installed$(RESET)"; \
	else \
		echo "$(CYAN)▶ Installing Ollama…$(RESET)"; \
		curl -fsSL https://ollama.com/install.sh | sh; \
	fi
	@if ollama list 2>/dev/null | grep -q "llama3.2:3b"; then \
		echo "$(GREEN)  ✓ llama3.2:3b present$(RESET)"; \
	else \
		echo "$(CYAN)▶ Pulling llama3.2:3b…$(RESET)"; \
		ollama pull llama3.2:3b; \
	fi

_node:
	@if ! command -v node >/dev/null 2>&1; then \
		echo "$(YELLOW)  ⚠  Node.js not found — desktop UI won't build.$(RESET)"; \
		echo "     Install: https://nodejs.org  (v18+)"; \
	else \
		echo "$(GREEN)  ✓ Node $(shell node --version) found$(RESET)"; \
		echo "$(CYAN)▶ npm install (desktop)…$(RESET)"; \
		cd $(DESKTOP_DIR) && npm install --silent; \
		echo "$(GREEN)  ✓ desktop deps$(RESET)"; \
	fi

_env:
	@if [ ! -f "$(AGENT_DIR)/.env" ]; then \
		cp $(AGENT_DIR)/.env.example $(AGENT_DIR)/.env; \
		echo "$(YELLOW)  ⚠  Created agent/.env from example — edit before running$(RESET)"; \
	fi

# ══════════════════════════════════════════════════════════════════════════════
#  BACKEND  (Rust audio daemon + Python agent)
# ══════════════════════════════════════════════════════════════════════════════
backend: _env
	@echo "$(CYAN)▶ Starting backend…$(RESET)"
	@if [ -f "$(AUDIO_BIN)" ]; then \
		if ! pgrep -x samantha-audio >/dev/null 2>&1; then \
			$(AUDIO_BIN) --socket $(SOCKET) --sample-rate 16000 \
				>/tmp/samantha-audio.log 2>&1 & \
			sleep 1; \
			echo "$(GREEN)  ✓ samantha-audio started$(RESET)"; \
		else \
			echo "$(GREEN)  ✓ samantha-audio already running$(RESET)"; \
		fi; \
	else \
		echo "$(YELLOW)  ⚠  Audio engine not built — voice via Python$(RESET)"; \
	fi
	@cd $(AGENT_DIR) && $(PYTHON) main.py

# ══════════════════════════════════════════════════════════════════════════════
#  PLATFORM  (Tauri desktop — dev mode)
# ══════════════════════════════════════════════════════════════════════════════
platform:
	@echo "$(CYAN)▶ Starting desktop UI (Tauri dev)…$(RESET)"
	@if ! command -v node >/dev/null 2>&1; then \
		echo "$(YELLOW)  ✗ Node.js not found. Install v18+ from nodejs.org$(RESET)"; exit 1; \
	fi
	@cd $(DESKTOP_DIR) && npm run tauri:dev

# ══════════════════════════════════════════════════════════════════════════════
#  RUN  (backend + platform in parallel)
# ══════════════════════════════════════════════════════════════════════════════
run: _env
	@echo "$(CYAN)▶ Starting backend + desktop…$(RESET)"
	@$(MAKE) backend &
	@sleep 2
	@$(MAKE) platform

# ══════════════════════════════════════════════════════════════════════════════
#  CLEAN
# ══════════════════════════════════════════════════════════════════════════════
clean:
	@echo "$(CYAN)▶ Cleaning…$(RESET)"
	@cd $(AUDIO_DIR) && $(CARGO) clean 2>/dev/null || true
	@rm -rf $(VENV)
	@rm -rf $(DESKTOP_DIR)/node_modules $(DESKTOP_DIR)/dist
	@rm -f $(AGENT_DIR)/memory.db /tmp/samantha-audio.log
	@echo "$(GREEN)  ✓ Clean$(RESET)"
