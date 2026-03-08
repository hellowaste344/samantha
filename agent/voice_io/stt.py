"""
voice_io/stt.py — Speech-to-text backed by faster-whisper (CTranslate2).

Modes
─────
  rust_bridge  (DEFAULT) — receives segmented audio from the Rust audio engine
               via Unix socket. Lowest latency: VAD + capture happen in Rust,
               Python only runs the Whisper model.

  voice        — pure-Python fallback: captures mic with sounddevice + faster-
               whisper. Works without the Rust binary, but adds ~30 ms overhead.

  text         — keyboard (stdin) input. No mic required.

Speed notes
───────────
  beam_size=1  — greedy decoding, 3–5× faster than beam_size=5.
                 Accuracy remains high for short desktop commands.
  WHISPER_MODEL=tiny (default) — ~32× realtime on CPU with int8 quantisation.
  Set WHISPER_MODEL=small in .env for higher accuracy at ~6× realtime.
"""
from __future__ import annotations

import asyncio
import os
import queue
import threading
import time
from typing import Optional

import config
from rich.console import Console
from rich.live    import Live
from rich.spinner import Spinner
from rich.text    import Text

_console = Console()

# ── Model singleton (shared across STT instances) ──────────────────────────────
_whisper_model = None
_model_lock    = threading.Lock()


def _load_model():
    global _whisper_model
    if _whisper_model is not None:
        return _whisper_model

    with _model_lock:
        if _whisper_model is not None:
            return _whisper_model

        try:
            from faster_whisper import WhisperModel
            _console.print(
                f"[dim][STT] Loading faster-whisper '{config.WHISPER_MODEL}' "
                f"(device={config.WHISPER_DEVICE}, compute={config.WHISPER_COMPUTE_TYPE})…[/dim]"
            )
            t0 = time.perf_counter()
            _whisper_model = WhisperModel(
                config.WHISPER_MODEL,
                device       = config.WHISPER_DEVICE,
                compute_type = config.WHISPER_COMPUTE_TYPE,
                cpu_threads  = config.WHISPER_CPU_THREADS,
                num_workers  = 2,   # parallel decode workers
            )
            elapsed = (time.perf_counter() - t0) * 1000
            _console.print(f"[dim][STT] faster-whisper ready ✓  ({elapsed:.0f} ms)[/dim]")
        except ImportError:
            _console.print(
                "[yellow][STT] faster-whisper not installed.\n"
                "  pip install faster-whisper[/yellow]"
            )
            return None
        except Exception as exc:
            _console.print(f"[red][STT] Model load error: {exc}[/red]")
            return None

    return _whisper_model


# ── STT class ─────────────────────────────────────────────────────────────────

class STT:
    """
    Synchronous STT interface used by the Orchestrator.
    Internally uses faster-whisper for transcription.
    """

    def __init__(self):
        requested = os.environ.get("STT_MODE") or config.STT_MODE or "rust_bridge"

        self._model  = _load_model()
        self._bridge = None
        self._q: queue.Queue[str] = queue.Queue()

        if self._model is None:
            self._mode = "text"
            _console.print("[yellow][STT] Falling back to text input.[/yellow]")
            return

        if requested == "text":
            self._mode = "text"
        elif requested == "rust_bridge":
            self._mode = "rust_bridge"
        else:
            self._mode = "voice"
            self._init_sounddevice()

    def _init_sounddevice(self):
        try:
            import sounddevice as sd  # noqa: F401
        except ImportError:
            _console.print(
                "[yellow][STT] sounddevice not installed. Falling back to text.[/yellow]"
            )
            self._mode = "text"

    # ── Public API ─────────────────────────────────────────────────────────────

    @property
    def mode(self) -> str:
        return self._mode

    @property
    def model(self):
        """Expose model for AudioBridge."""
        return self._model

    def set_bridge(self, bridge):
        """Called by Orchestrator after AudioBridge is connected."""
        self._bridge = bridge

    def feed(self, text: str):
        """Called by the bridge consumer loop to inject transcripts."""
        self._q.put(text)

    def listen(self) -> str:
        """Block until the user provides input; return text string."""
        if self._mode == "text":
            return self._listen_text()
        if self._mode == "rust_bridge":
            return self._listen_bridge()
        return self._listen_voice()

    # ── Text mode ──────────────────────────────────────────────────────────────

    def _listen_text(self) -> str:
        try:
            return input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            return "exit"

    # ── Rust bridge mode ───────────────────────────────────────────────────────

    def _listen_bridge(self) -> str:
        """
        Block until the Rust engine sends a complete transcribed utterance.
        The AudioBridge feeds transcripts into self._q from its async loop.
        """
        try:
            with Live(
                Spinner("dots2", text=Text("  Samantha is listening…", style="bold green")),
                refresh_per_second=10,
                transient=True,
                console=_console,
            ):
                while True:
                    try:
                        return self._q.get(timeout=0.1)
                    except queue.Empty:
                        continue
        except KeyboardInterrupt:
            return "exit"

    # ── Pure-Python voice mode (sounddevice fallback) ──────────────────────────

    def _listen_voice(self) -> str:
        import numpy as np
        import sounddevice as sd

        RATE          = config.AUDIO_SAMPLE_RATE
        BLOCK         = int(RATE * 0.02)   # 20 ms frames
        MAX_SILENCE_S = config.MIC_PAUSE_DURATION
        MAX_RECORD_S  = 30
        ENERGY_THRESH = config.MIC_ENERGY_THRESHOLD

        frames: list[np.ndarray] = []
        silence_blocks = 0
        max_silence    = int(MAX_SILENCE_S * RATE / BLOCK)
        max_blocks     = int(MAX_RECORD_S  * RATE / BLOCK)
        speaking       = False

        with Live(
            Spinner("dots2", text=Text("  Samantha is listening…", style="bold green")),
            refresh_per_second=10,
            transient=True,
            console=_console,
        ):
            with sd.InputStream(samplerate=RATE, channels=1, dtype="float32",
                                blocksize=BLOCK) as stream:
                for _ in range(max_blocks):
                    block, _ = stream.read(BLOCK)
                    energy   = float(np.abs(block).mean())

                    if energy > ENERGY_THRESH:
                        speaking = True
                        silence_blocks = 0
                    elif speaking:
                        silence_blocks += 1

                    if speaking:
                        frames.append(block.copy())

                    if speaking and silence_blocks >= max_silence:
                        break

        if not frames:
            return ""

        audio = np.concatenate(frames).flatten()

        with Live(
            Spinner("dots", text=Text("  Processing speech…", style="dim cyan")),
            refresh_per_second=10,
            transient=True,
            console=_console,
        ):
            try:
                assert self._model is not None
                segments, info = self._model.transcribe(
                    audio,
                    language                   = config.STT_LANGUAGE,
                    beam_size                  = 1,          # greedy — fastest
                    vad_filter                 = True,
                    condition_on_previous_text = False,
                )
                text = " ".join(seg.text for seg in segments).strip()
                if config.DEBUG:
                    _console.print(
                        f"[dim][STT] {text!r}  lang={info.language}[/dim]"
                    )
                return text
            except Exception as exc:
                if config.DEBUG:
                    _console.print(f"[red][STT] Transcription error: {exc}[/red]")
                return ""
