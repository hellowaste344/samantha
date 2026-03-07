"""
config.py — Central configuration for Samantha v2.

Architecture change:
  Audio pipeline is now split between the Rust audio engine
  (samantha-audio binary) and Python (faster-whisper).

  STT_MODE=rust_bridge  (default) — Rust handles capture + VAD,
                                    Python handles transcription only.
  STT_MODE=voice        — Python-only fallback (sounddevice + faster-whisper).
  STT_MODE=text         — Keyboard input, no mic.
"""

import os

from dotenv import load_dotenv

load_dotenv()

# ── HuggingFace Hub token ──────────────────────────────────────────────────────
# faster-whisper downloads model weights from HF Hub. Without a token, HF
# rate-limits anonymous requests which can slow or fail downloads.
# Get a free read-only token: https://huggingface.co/settings/tokens
# Add  HF_TOKEN=<your_token>  to agent/.env
_hf_token = os.getenv("HF_TOKEN", "").strip()
if _hf_token:
    os.environ["HF_TOKEN"] = _hf_token  # huggingface_hub reads this
    os.environ["HUGGING_FACE_HUB_TOKEN"] = _hf_token  # legacy alias
else:
    import warnings as _warnings

    _warnings.filterwarnings(
        "ignore",
        message=".*unauthenticated requests.*",
    )

# ── Agent Identity ─────────────────────────────────────────────────────────────
AGENT_NAME = "Samantha"
DOMAIN = os.getenv("DOMAIN", "zenonai.net")
GREETING = (
    "Hello! I'm Samantha, your AI assistant. "
    "I can browse the web, open apps, send emails, "
    "and answer your questions — all running locally. "
    "What would you like to do?"
)

# ── Runtime ────────────────────────────────────────────────────────────────────
DOCKER_MODE = os.getenv("DOCKER_MODE", "false").lower() == "true"
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# ── LLM — Ollama ──────────────────────────────────────────────────────────────
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "deepseek-r1:7b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "120"))
OLLAMA_AUTO_START = os.getenv("OLLAMA_AUTO_START", "true").lower() == "true"

LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "1024"))

# ── STT — faster-whisper (replaces openai-whisper) ────────────────────────────
#
# WHISPER_MODEL options (speed vs accuracy):
#   tiny   → ~32x realtime  (lowest accuracy)
#   base   → ~16x realtime
#   small  → ~6x realtime   ← recommended default
#   medium → ~2x realtime
#   large-v3 → 1x realtime  (highest accuracy)
#
# WHISPER_COMPUTE_TYPE options:
#   int8        → fastest CPU, slight quality loss
#   int8_float16 → fast GPU
#   float16     → GPU, full quality
#   float32     → CPU, full quality, slower
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")
WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")  # or "cuda"
WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
WHISPER_CPU_THREADS = int(os.getenv("WHISPER_CPU_THREADS", "4"))

# STT_MODE: rust_bridge | voice | text
STT_MODE = os.getenv("STT_MODE", "text" if DOCKER_MODE else "rust_bridge")
STT_LANGUAGE = os.getenv("STT_LANGUAGE", "en")

# Mic settings (voice fallback mode only)
AUDIO_SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
MIC_ENERGY_THRESHOLD = float(os.getenv("MIC_ENERGY_THRESHOLD", "0.01"))
MIC_PAUSE_DURATION = float(os.getenv("MIC_PAUSE_DURATION", "1.2"))  # seconds

# Rust audio engine socket path
AUDIO_SOCKET = os.getenv("AUDIO_SOCKET", "/tmp/samantha_audio.sock")

# ── TTS ────────────────────────────────────────────────────────────────────────
TTS_ENGINE = os.getenv("TTS_ENGINE", "none" if DOCKER_MODE else "edge")
TTS_EDGE_VOICE = os.getenv("TTS_EDGE_VOICE", "aria")

TTS_PIPER_VOICE = os.getenv("TTS_PIPER_VOICE", "lessac")
TTS_PIPER_MODELS_DIR = os.path.expanduser(
    os.getenv("TTS_PIPER_MODELS_DIR", "~/.samantha_piper_voices")
)
TTS_VOICE_RATE = int(os.getenv("TTS_VOICE_RATE", "175"))
TTS_VOLUME_RATE = int(os.getenv("TTS_VOLUME_RATE", "1"))

# ── Browser — Playwright ───────────────────────────────────────────────────────
BROWSER_HEADLESS = (
    os.getenv("BROWSER_HEADLESS", "true" if DOCKER_MODE else "false").lower() == "true"
)
BROWSER_SLOW_MO = 60
BROWSER_TIMEOUT = 15_000
BROWSER_PROFILE = os.path.expanduser(
    os.getenv("BROWSER_PROFILE", "~/.samantha_browser_profile")
)

# ── Orchestrator ───────────────────────────────────────────────────────────────
MAX_ACTION_RETRIES = 3
CONTEXT_WINDOW_SIZE = 10
MIN_CONFIDENCE = 0.50
MEMORY_DB = os.getenv("MEMORY_DB", "memory.db")

# ── Local API bridge (for frontend dashboard) ──────────────────────────────────
API_PORT = int(os.getenv("API_PORT", "7799"))
API_ENABLED = os.getenv("API_ENABLED", "true").lower() == "true"
