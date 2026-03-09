"""
config.py — Central configuration for Samantha.

Architecture:
  Audio pipeline is split between the Rust audio engine (samantha-audio binary)
  and Python (faster-whisper).

  STT_MODE=rust_bridge  (default) — Rust handles capture + VAD,
                                    Python handles transcription only.
  STT_MODE=voice        — Python-only fallback (sounddevice + faster-whisper).
  STT_MODE=text         — Keyboard input, no mic.
"""

import os
import random

from dotenv import load_dotenv

load_dotenv()

# ── HuggingFace Hub token ──────────────────────────────────────────────────────
_hf_token = os.getenv("HF_TOKEN", "").strip()
if _hf_token:
    os.environ["HF_TOKEN"] = _hf_token
    os.environ["HUGGING_FACE_HUB_TOKEN"] = _hf_token  # legacy alias
else:
    import warnings as _warnings

    _warnings.filterwarnings("ignore", message=".*unauthenticated requests.*")

# ── Agent Identity ─────────────────────────────────────────────────────────────
AGENT_NAME = "Samantha"
DOMAIN = os.getenv("DOMAIN", "zenonai.net")
GREETING_OPTIONS = [
    "Hello! I'm Samantha, your AI assistant. What would you like to do Today?",
    "I'm your AI assistant Samantha, if you need help just call me.",
    "Hi there, What's in your mind today?",
    "You're back, Where shall we begin?",
]
GREETING = GREETING_OPTIONS[random.randint(0, 3)]

# ── Runtime ────────────────────────────────────────────────────────────────────
DEBUG = os.getenv("DEBUG", "false").lower() == "true"

# ── LLM — Ollama ──────────────────────────────────────────────────────────────
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
# llama3.2:3b is ~3× faster than deepseek-r1:7b for structured JSON plans.
# Switch to mistral or deepseek-r1:7b in .env if you prefer higher accuracy.
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "60"))
OLLAMA_AUTO_START = os.getenv("OLLAMA_AUTO_START", "true").lower() == "true"

LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.1"))
# JSON plans are compact — 512 tokens is more than enough and cuts latency.
LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "512"))
# Limit context window fed to Ollama to reduce prefill time.
LLM_NUM_CTX = int(os.getenv("LLM_NUM_CTX", "2048"))

# ── STT — faster-whisper ───────────────────────────────────────────────────────
#
# WHISPER_MODEL options (speed vs accuracy):
#   tiny   → ~32x realtime  (lowest accuracy)   ← fast default
#   base   → ~16x realtime
#   small  → ~6x realtime   (better accuracy)
#   medium → ~2x realtime
#   large-v3 → 1x realtime  (highest accuracy)
#
# WHISPER_COMPUTE_TYPE options:
#   int8        → fastest CPU, slight quality loss  ← default
#   int8_float16 → fast GPU
#   float16     → GPU, full quality
#   float32     → CPU, full quality, slower
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "small")


def _auto_detect_device() -> str:
    """Return 'cuda' if a CUDA-capable GPU is visible to CTranslate2, else 'cpu'.

    faster-whisper is built on CTranslate2 so we query it directly — no
    torch dependency required.  If the env var is set explicitly it always
    wins so users can force cpu/cuda in .env.
    """
    override = os.getenv("WHISPER_DEVICE", "").strip()
    if override:
        return override
    try:
        import ctranslate2
        if ctranslate2.get_cuda_device_count() > 0:
            return "cuda"
    except Exception:
        pass
    return "cpu"


def _auto_detect_compute_type(device: str) -> str:
    """Return the fastest compute type for the detected device.

    GPU:  float16  — full precision, maximum throughput on CUDA
    CPU:  int8     — quantised, fastest on x86 without accuracy loss for STT
    """
    override = os.getenv("WHISPER_COMPUTE_TYPE", "").strip()
    if override:
        return override
    return "float16" if device == "cuda" else "int8"


WHISPER_DEVICE = _auto_detect_device()
WHISPER_COMPUTE_TYPE = _auto_detect_compute_type(WHISPER_DEVICE)
WHISPER_CPU_THREADS = int(os.getenv("WHISPER_CPU_THREADS", "4"))

# STT_MODE: rust_bridge | voice | text
STT_MODE = os.getenv("STT_MODE", "rust_bridge")
STT_LANGUAGE = os.getenv("STT_LANGUAGE", "en")

# Mic settings (voice fallback mode only)
AUDIO_SAMPLE_RATE = int(os.getenv("AUDIO_SAMPLE_RATE", "16000"))
MIC_ENERGY_THRESHOLD = float(os.getenv("MIC_ENERGY_THRESHOLD", "0.01"))
MIC_PAUSE_DURATION = float(os.getenv("MIC_PAUSE_DURATION", "1.5"))

# Rust audio engine socket path
AUDIO_SOCKET = os.getenv("AUDIO_SOCKET", "/tmp/samantha_audio.sock")

# ── TTS ────────────────────────────────────────────────────────────────────────
TTS_ENGINE = os.getenv("TTS_ENGINE", "edge")
TTS_EDGE_VOICE = os.getenv("TTS_EDGE_VOICE", "aria")

TTS_PIPER_VOICE = os.getenv("TTS_PIPER_VOICE", "lessac")
TTS_PIPER_MODELS_DIR = os.path.expanduser(
    os.getenv("TTS_PIPER_MODELS_DIR", "~/.samantha_piper_voices")
)
TTS_VOICE_RATE = int(os.getenv("TTS_VOICE_RATE", "175"))
TTS_VOLUME_RATE = int(os.getenv("TTS_VOLUME_RATE", "1"))

# ── Browser — Playwright ───────────────────────────────────────────────────────
BROWSER_HEADLESS = os.getenv("BROWSER_HEADLESS", "false").lower() == "true"
BROWSER_SLOW_MO = 60
BROWSER_TIMEOUT = 15_000
BROWSER_PROFILE = os.path.expanduser(
    os.getenv("BROWSER_PROFILE", "~/.samantha_browser_profile")
)

# ── Orchestrator ───────────────────────────────────────────────────────────────
MAX_ACTION_RETRIES = 3
CONTEXT_WINDOW_SIZE = 10
MIN_CONFIDENCE = 0.80
MEMORY_DB = os.getenv("MEMORY_DB", "memory.db")

# ── Local API bridge (for frontend dashboard) ──────────────────────────────────
API_PORT = int(os.getenv("API_PORT", "7799"))
API_ENABLED = os.getenv("API_ENABLED", "true").lower() == "true"

# ── Screen capture pipeline ────────────────────────────────────────────────────
# Which monitor to capture (1 = primary, 2 = secondary, etc.)
SCREEN_MONITOR = int(os.getenv("SCREEN_MONITOR", "1"))

# YOLOv8 model file. "yolov8n.pt" is auto-downloaded from ultralytics on first use.
# Swap in a UI-specific model (e.g. a fine-tuned YOLO for buttons/icons/fields)
# by pointing this at your .pt file path.
YOLO_MODEL_PATH = os.getenv("YOLO_MODEL_PATH", "yolov8n.pt")

# OCR language code.
# PaddleOCR codes: https://paddlepaddle.github.io/PaddleOCR/latest/en/ppocr/blog/multi_languages.html
# Tesseract codes: run `tesseract --list-langs`
OCR_LANGUAGE = os.getenv("OCR_LANGUAGE", "en")
