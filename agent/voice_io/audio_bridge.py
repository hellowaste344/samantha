"""
voice_io/audio_bridge.py — Unix socket client that receives audio events
from the Rust audio engine (samantha-audio) and feeds utterances to
faster-whisper for transcription.

Protocol:
  {"type":"speech_start","sample_rate":16000}
  {"type":"audio_chunk","data":"<base64 f32-le>","n_samples":N}
  {"type":"speech_end","duration_ms":1250}
  {"type":"ping"}
"""
from __future__ import annotations

import asyncio
import base64
import json
import numpy as np
import os
import socket
import struct
import time
from pathlib import Path
from typing import AsyncIterator, Optional

import config
from rich.console import Console

_console = Console()

SOCKET_PATH = Path(os.getenv("AUDIO_SOCKET", "/tmp/samantha_audio.sock"))


class AudioBridge:
    """
    Async client to the Rust audio engine.

    Usage:
        bridge = AudioBridge()
        async for transcript in bridge.utterances():
            print(transcript)
    """

    def __init__(self, whisper_model):
        self._model   = whisper_model   # faster-whisper WhisperModel instance
        self._sock:   Optional[asyncio.StreamReader] = None
        self._writer: Optional[asyncio.StreamWriter] = None
        self._connected = False

    async def connect(self, retries: int = 10, delay: float = 0.5):
        """Connect (or reconnect) to the Rust engine socket."""
        for attempt in range(1, retries + 1):
            try:
                reader, writer = await asyncio.open_unix_connection(str(SOCKET_PATH))
                self._sock   = reader
                self._writer = writer
                self._connected = True
                _console.print(
                    "[dim][AudioBridge] Connected to Rust audio engine ✓[/dim]"
                )
                return
            except (FileNotFoundError, ConnectionRefusedError):
                if attempt == retries:
                    raise RuntimeError(
                        f"Cannot connect to Rust audio engine at {SOCKET_PATH}.\n"
                        "  Is samantha-audio running?  Run:  samantha-audio &"
                    )
                await asyncio.sleep(delay)

    async def utterances(self) -> AsyncIterator[str]:
        """
        Async generator that yields one transcribed string per detected utterance.
        Automatically reconnects if the Rust engine restarts.
        """
        while True:
            if not self._connected:
                try:
                    await self.connect()
                except RuntimeError as e:
                    _console.print(f"[red]{e}[/red]")
                    await asyncio.sleep(2)
                    continue

            async for transcript in self._read_loop():
                yield transcript

    async def _read_loop(self) -> AsyncIterator[str]:
        """Read events from socket, accumulate audio, transcribe on speech_end."""
        pcm_chunks: list[np.ndarray] = []
        sample_rate = config.AUDIO_SAMPLE_RATE
        in_speech   = False

        try:
            assert self._sock is not None
            while True:
                line = await self._sock.readline()
                if not line:
                    _console.print("[yellow][AudioBridge] Rust engine disconnected.[/yellow]")
                    self._connected = False
                    return

                try:
                    msg = json.loads(line.decode().strip())
                except json.JSONDecodeError:
                    continue

                mtype = msg.get("type", "")

                if mtype == "speech_start":
                    sample_rate = msg.get("sample_rate", config.AUDIO_SAMPLE_RATE)
                    pcm_chunks.clear()
                    in_speech = True

                elif mtype == "audio_chunk" and in_speech:
                    raw   = base64.b64decode(msg["data"])
                    arr   = np.frombuffer(raw, dtype=np.float32).copy()
                    pcm_chunks.append(arr)

                elif mtype == "speech_end" and in_speech:
                    in_speech = False
                    if pcm_chunks:
                        audio = np.concatenate(pcm_chunks)
                        transcript = await asyncio.get_event_loop().run_in_executor(
                            None, self._transcribe, audio, sample_rate
                        )
                        if transcript:
                            yield transcript
                    pcm_chunks.clear()

                # pings are silently ignored

        except (asyncio.IncompleteReadError, ConnectionResetError, BrokenPipeError):
            _console.print("[yellow][AudioBridge] Connection lost, reconnecting…[/yellow]")
            self._connected = False

    def _transcribe(self, audio: np.ndarray, sample_rate: int) -> str:
        """
        Run faster-whisper transcription synchronously (called via executor).
        Returns stripped transcript string, or empty string on failure.
        """
        try:
            t0 = time.perf_counter()
            segments, info = self._model.transcribe(
                audio,
                language          = config.STT_LANGUAGE,
                beam_size         = 5,
                vad_filter        = True,           # faster-whisper built-in VAD
                vad_parameters    = {
                    "min_silence_duration_ms": 500,
                    "threshold": 0.5,
                },
                condition_on_previous_text = False,
            )
            text = " ".join(seg.text for seg in segments).strip()
            elapsed = (time.perf_counter() - t0) * 1000
            if config.DEBUG and text:
                _console.print(
                    f"[dim][STT] {text!r}  ({elapsed:.0f} ms  "
                    f"lang={info.language} p={info.language_probability:.2f})[/dim]"
                )
            return text
        except Exception as exc:
            if config.DEBUG:
                _console.print(f"[red][STT error] {exc}[/red]")
            return ""

    async def close(self):
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except Exception:
                pass
        self._connected = False
