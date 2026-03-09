"""
voice_io/tts.py — Text-to-speech with four engine tiers.

  Tier 0 — none      (Docker default — silent no-op, text output only)
  Tier 1 — edge-tts  (DEFAULT on host — neural, 300+ voices, pure Python,
                       zero system deps, works on ALL distros including Arch)
  Tier 2 — piper-tts (offline fallback — neural, needs espeak-ng)
  Tier 3 — pyttsx3   (last resort — system voice, fully offline)

Audio playback cascade (tried in order, first success wins):
  1. pydub + ffmpeg
  2. sounddevice + soundfile  (skipped for .mp3 — soundfile can't decode it)
  3. ffplay subprocess
  4. mpg123 subprocess
  5. aplay via ffmpeg wav conversion (ALSA, Linux only)
"""

from __future__ import annotations

import asyncio
import os
import subprocess
import tempfile
import threading
import time
import urllib.request
from pathlib import Path
from typing import Dict, Optional

import config

# Detect WSL once at module load — /proc/version contains "microsoft" on WSL2
_IS_WSL = (
    os.path.exists("/proc/version")
    and "microsoft" in open("/proc/version").read().lower()
)


# ── Edge-TTS voice roster ──────────────────────────────────────────────────────
EDGE_VOICES: Dict[str, Dict] = {
    "aria": {
        "display": "Aria (US Female, warm)",
        "gender": "female",
        "accent": "american",
        "edge_name": "en-US-AriaNeural",
    },
    "jenny": {
        "display": "Jenny (US Female, professional)",
        "gender": "female",
        "accent": "american",
        "edge_name": "en-US-JennyNeural",
    },
    "guy": {
        "display": "Guy (US Male)",
        "gender": "male",
        "accent": "american",
        "edge_name": "en-US-GuyNeural",
    },
    "davis": {
        "display": "Davis (US Male, casual)",
        "gender": "male",
        "accent": "american",
        "edge_name": "en-US-DavisNeural",
    },
    "ryan": {
        "display": "Ryan (British Male)",
        "gender": "male",
        "accent": "british",
        "edge_name": "en-GB-RyanNeural",
    },
    "sonia": {
        "display": "Sonia (British Female)",
        "gender": "female",
        "accent": "british",
        "edge_name": "en-GB-SoniaNeural",
    },
    "natasha": {
        "display": "Natasha (Australian Female)",
        "gender": "female",
        "accent": "australian",
        "edge_name": "en-AU-NatashaNeural",
    },
    "william": {
        "display": "William (Australian Male)",
        "gender": "male",
        "accent": "australian",
        "edge_name": "en-AU-WilliamNeural",
    },
    "neerja": {
        "display": "Neerja (Indian Female)",
        "gender": "female",
        "accent": "indian",
        "edge_name": "en-IN-NeerjaNeural",
    },
    "prabhat": {
        "display": "Prabhat (Indian Male)",
        "gender": "male",
        "accent": "indian",
        "edge_name": "en-IN-PrabhatNeural",
    },
}

# ── Piper offline voice roster ─────────────────────────────────────────────────
PIPER_VOICES: Dict[str, Dict] = {
    "lessac": {
        "display": "Lessac (US Female)",
        "gender": "female",
        "accent": "american",
        "model": "en_US-lessac-medium",
        "lang_path": "en/en_US",
    },
    "amy": {
        "display": "Amy (US Female)",
        "gender": "female",
        "accent": "american",
        "model": "en_US-amy-medium",
        "lang_path": "en/en_US",
    },
    "ryan_us": {
        "display": "Ryan (US Male)",
        "gender": "male",
        "accent": "american",
        "model": "en_US-ryan-medium",
        "lang_path": "en/en_US",
    },
    "danny": {
        "display": "Danny (US Male, light)",
        "gender": "male",
        "accent": "american",
        "model": "en_US-danny-low",
        "lang_path": "en/en_US",
    },
    "alan": {
        "display": "Alan (British Male)",
        "gender": "male",
        "accent": "british",
        "model": "en_GB-alan-medium",
        "lang_path": "en/en_GB",
    },
    "jenny_gb": {
        "display": "Jenny (British Female)",
        "gender": "female",
        "accent": "british",
        "model": "en_GB-jenny_dioco-medium",
        "lang_path": "en/en_GB",
    },
}

# ── Unified aliases ────────────────────────────────────────────────────────────
VOICE_ALIASES: Dict[str, str] = {
    "male": "guy",
    "female": "aria",
    "default": "aria",
    "american": "aria",
    "us": "aria",
    "british": "ryan",
    "uk": "ryan",
    "australian": "natasha",
    "au": "natasha",
    "indian": "neerja",
    # Legacy piper keys — map to edge equivalents
    "lessac": "aria",
    "alan": "ryan",
    "danny": "davis",
}

# Edge key → closest piper key (used when engine=piper)
_EDGE_TO_PIPER: Dict[str, str] = {
    "aria": "lessac",
    "jenny": "amy",
    "guy": "ryan_us",
    "davis": "danny",
    "ryan": "alan",
    "sonia": "jenny_gb",
    "natasha": "lessac",
    "william": "ryan_us",
    "neerja": "lessac",
    "prabhat": "ryan_us",
}

HF_BASE = "https://huggingface.co/rhasspy/piper-voices/resolve/main"


# ══════════════════════════════════════════════════════════════════════════════
class TTS:
    def __init__(self):
        self._lock = threading.Lock()
        self._active_engine = "none"
        self._current_voice = config.TTS_EDGE_VOICE
        self._edge_voice_name: str = ""
        self._piper_voice = None
        self._pyttsx3_engine = None
        # Reusable event loop for edge-tts synthesis (created once per session)
        self._edge_loop: Optional[asyncio.AbstractEventLoop] = None

    # ── Lifecycle ──────────────────────────────────────────────────────────────
    async def setup(self):
        """
        Initialise TTS engine in priority order based on TTS_ENGINE config.

          none    — silent no-op (Docker default — no audio device)
          edge    — edge-tts neural voices
          piper   — piper-tts offline neural voices
          auto    — try edge -> piper -> pyttsx3
          pyttsx3 — system voice (last resort)
        """
        pref = config.TTS_ENGINE.lower()

        if pref == "none":
            self._active_engine = "none"
            print("[TTS] Speech disabled (TTS_ENGINE=none).")
            print("[TTS]   To enable: set TTS_ENGINE=edge in .env and configure")
            print("[TTS]   audio passthrough in docker-compose.yml.")
            return

        if pref in ("edge", "auto"):
            if await self._init_edge(config.TTS_EDGE_VOICE):
                return

        if pref in ("piper", "auto"):
            if await self._init_piper(config.TTS_PIPER_VOICE):
                return

        await self._init_pyttsx3()

    async def teardown(self):
        if self._edge_loop and not self._edge_loop.is_closed():
            self._edge_loop.close()

    # ── Engine: edge-tts ──────────────────────────────────────────────────────
    async def _init_edge(self, voice_key: str) -> bool:
        try:
            import edge_tts  # noqa: F401

            resolved = VOICE_ALIASES.get(voice_key.lower(), voice_key.lower())
            info = EDGE_VOICES.get(resolved)
            if info:
                self._edge_voice_name = info["edge_name"]
                self._current_voice = resolved
            else:
                self._edge_voice_name = voice_key
                self._current_voice = voice_key
            self._active_engine = "edge"
            # Create the dedicated event loop for synthesis here, once
            self._edge_loop = asyncio.new_event_loop()
            display = (info or {}).get("display", self._edge_voice_name)
            print(f"[TTS] edge-tts ready ✓  voice: {display}")
            return True
        except ImportError:
            print("[TTS] edge-tts not installed.  Install: pip install edge-tts")
            print("[TTS] Trying piper-tts next…")
            return False
        except Exception as exc:
            print(f"[TTS] edge-tts init failed ({type(exc).__name__}): {exc}")
            return False

    def _speak_edge(self, text: str):
        """
        Synthesise text with edge-tts and play it.
        Reuses a dedicated event loop (created once in _init_edge) so we never
        spin up a new loop per utterance.
        """
        import edge_tts

        async def _synthesise(tmp_path: str):
            communicate = edge_tts.Communicate(text, self._edge_voice_name)
            await communicate.save(tmp_path)

        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            tmp = f.name
        try:
            self._edge_loop.run_until_complete(_synthesise(tmp))
            self._play_audio_file(tmp)
        except Exception as exc:
            if config.DEBUG:
                print(f"[TTS] edge-tts speak error: {exc}")
        finally:
            try:
                os.unlink(tmp)
            except OSError:
                pass

    def _play_audio_file(self, path: str):
        """
        Play an audio file via the best available backend.

        WSL:            wslpath → ffplay.exe → PowerShell WMPlayer COM
        Linux / macOS:  pydub → sounddevice → ffplay → mpg123 → aplay+ffmpeg
        """
        if _IS_WSL:
            self._play_audio_wsl(path)
            return

        # 1. pydub (pip install pydub + system ffmpeg)
        try:
            from pydub import AudioSegment
            from pydub.playback import play as pydub_play

            pydub_play(AudioSegment.from_file(path))
            return
        except Exception:
            pass

        # 2. sounddevice + soundfile — cannot decode MP3 natively
        if not path.endswith(".mp3"):
            try:
                import sounddevice as sd
                import soundfile as sf

                data, sr = sf.read(path)
                sd.play(data, sr)
                sd.wait()
                return
            except Exception:
                pass

        # 3. ffplay
        try:
            subprocess.run(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
                check=True,
                timeout=120,
            )
            return
        except (
            FileNotFoundError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ):
            pass

        # 4. mpg123
        try:
            subprocess.run(["mpg123", "-q", path], check=True, timeout=120)
            return
        except (
            FileNotFoundError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ):
            pass

        # 5. aplay via ffmpeg wav conversion (ALSA, Linux)
        try:
            wav = path + "_play.wav"
            subprocess.run(
                ["ffmpeg", "-y", "-i", path, wav],
                check=True,
                capture_output=True,
                timeout=30,
            )
            subprocess.run(["aplay", "-q", wav], check=True, timeout=120)
            os.unlink(wav)
            return
        except Exception:
            pass

        print(
            "[TTS] ⚠  No audio playback backend found.\n"
            "         Install one of: pip install pydub | pip install sounddevice soundfile\n"
            "         Or system pkg: ffmpeg | mpg123"
        )

    def _play_audio_wsl(self, path: str):
        """
        WSL audio playback — convert Linux path to Windows path then play
        via Windows-side tools (no ALSA / PulseAudio needed).

        Cascade:
          1. ffplay.exe  — if Windows ffmpeg is installed
          2. WMPlayer COM object via powershell.exe  — built into Windows
        """
        try:
            win_path = (
                subprocess.check_output(
                    ["wslpath", "-w", path], stderr=subprocess.DEVNULL
                )
                .decode()
                .strip()
            )
        except Exception:
            print("[TTS] wslpath failed — cannot play audio in WSL")
            return

        # 1. ffplay.exe (Windows ffmpeg)
        try:
            subprocess.run(
                ["ffplay.exe", "-nodisp", "-autoexit", "-loglevel", "quiet", win_path],
                check=True,
                timeout=120,
            )
            return
        except FileNotFoundError:
            pass  # ffplay.exe not installed — try next
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return

        # 2. Windows Media Player COM via PowerShell (built into all Windows installs)
        try:
            ps_script = (
                "$wmp = New-Object -ComObject WMPlayer.OCX.7; "
                f"$wmp.URL = '{win_path}'; "
                "$wmp.controls.play(); "
                "do { Start-Sleep -Milliseconds 200 } "
                "while ($wmp.playState -ne 1); "
                "$wmp.close()"
            )
            subprocess.run(
                ["powershell.exe", "-WindowStyle", "Hidden", "-Command", ps_script],
                check=True,
                timeout=120,
            )
            return
        except Exception:
            pass

        print(
            "[TTS] WSL audio playback failed.\n"
            "  Install Windows ffmpeg and add to PATH: https://ffmpeg.org/download.html"
        )

    # ── Engine: piper ──────────────────────────────────────────────────────────
    async def _init_piper(self, voice_key: str) -> bool:
        try:
            await asyncio.to_thread(self._load_piper_voice, voice_key)
            self._active_engine = "piper"
            return True
        except ImportError:
            print(
                "[TTS] piper-tts not installed.\n"
                "      Install:       pip install piper-tts sounddevice\n"
                "      Arch Linux:    sudo pacman -S espeak-ng\n"
                "      Debian/Ubuntu: sudo apt install libespeak-ng1\n"
                "      Trying pyttsx3 as last resort…"
            )
            return False
        except RuntimeError as exc:
            print(f"[TTS] Piper model load failed: {exc}\n  Trying pyttsx3…")
            return False
        except Exception as exc:
            print(
                f"[TTS] Piper init failed ({type(exc).__name__}): {exc}\n  Trying pyttsx3…"
            )
            return False

    def _resolve_piper_key(self, voice_key: str) -> str:
        resolved = VOICE_ALIASES.get(voice_key.lower(), voice_key.lower())
        return _EDGE_TO_PIPER.get(resolved, resolved)

    def _load_piper_voice(self, voice_key: str):
        from piper.voice import PiperVoice

        piper_key = self._resolve_piper_key(voice_key)
        info = PIPER_VOICES.get(piper_key)
        model_name = info["model"] if info else piper_key
        lang_path = info["lang_path"] if info else "en/en_US"

        models_dir = Path(config.TTS_PIPER_MODELS_DIR)
        models_dir.mkdir(parents=True, exist_ok=True)

        onnx_path = models_dir / f"{model_name}.onnx"
        json_path = models_dir / f"{model_name}.onnx.json"

        if not onnx_path.exists() or not json_path.exists():
            self._download_piper_voice(model_name, lang_path, models_dir)

        print(f"[TTS] Loading Piper voice: {model_name}")
        self._piper_voice = PiperVoice.load(str(onnx_path), config_path=str(json_path))
        self._current_voice = piper_key
        display = PIPER_VOICES.get(piper_key, {}).get("display", model_name)
        print(f"[TTS] Piper ready ✓  voice: {display}")

    def _download_piper_voice(self, model_name: str, lang_path: str, models_dir: Path):
        print(f"[TTS] Downloading Piper voice '{model_name}' (one-time download)…")
        base = f"{HF_BASE}/{lang_path}/{model_name}"
        for filename in [f"{model_name}.onnx", f"{model_name}.onnx.json"]:
            url = f"{base}/{filename}"
            dest = models_dir / filename
            print(f"[TTS]   ↓ {url}")
            last_exc: Optional[Exception] = None
            for attempt in range(1, 4):
                try:
                    urllib.request.urlretrieve(url, dest)
                    last_exc = None
                    break
                except Exception as exc:
                    last_exc = exc
                    dest.unlink(missing_ok=True)
                    if attempt < 3:
                        print(f"[TTS]   ↺ attempt {attempt} failed ({exc}), retrying…")
                        time.sleep(1.5 * attempt)
            if last_exc is not None:
                for orphan in [
                    models_dir / f"{model_name}.onnx",
                    models_dir / f"{model_name}.onnx.json",
                ]:
                    orphan.unlink(missing_ok=True)
                raise RuntimeError(
                    f"Failed to download '{filename}' after 3 attempts: {last_exc}\n"
                    f"  URL: {url}"
                ) from last_exc
        print(f"[TTS] Voice '{model_name}' downloaded ✓")

    def _speak_piper(self, text: str):
        """Synthesise with Piper and play via the WSL-aware audio cascade.

        Previously this wrote raw PCM directly to sounddevice, which has no
        ALSA/PortAudio device on WSL and would silently crash.  Writing to a
        temporary WAV file and routing through _play_audio_file ensures the
        same playback cascade (ffplay.exe → PowerShell WMP on WSL;
        pydub → sounddevice → ffplay → mpg123 → aplay on Linux/macOS) is used
        for Piper output as for edge-tts output.
        """
        import wave

        try:
            import numpy as np

            chunks = list(self._piper_voice.synthesize_stream_raw(text))
            if not chunks:
                return
            audio = np.frombuffer(b"".join(chunks), dtype=np.int16)
            rate  = self._piper_voice.config.sample_rate

            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                tmp = f.name
            try:
                with wave.open(tmp, "wb") as wf:
                    wf.setnchannels(1)
                    wf.setsampwidth(2)   # int16 = 2 bytes per sample
                    wf.setframerate(rate)
                    wf.writeframes(audio.tobytes())
                self._play_audio_file(tmp)   # WSL-aware playback cascade
            finally:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
        except ImportError:
            print("[TTS] numpy not installed. Run: pip install numpy")
        except Exception as exc:
            if config.DEBUG:
                print(f"[TTS] Piper speak error: {exc}")

    # ── Engine: pyttsx3 ────────────────────────────────────────────────────────
    async def _init_pyttsx3(self):
        try:
            import pyttsx3

            engine = pyttsx3.init()
            engine.setProperty("rate", config.TTS_VOICE_RATE)
            engine.setProperty("volume", float(config.TTS_VOLUME_RATE))
            voices = engine.getProperty("voices") or []
            female = next(
                (
                    v
                    for v in voices
                    if any(
                        k in (v.name or "").lower()
                        for k in ("female", "zira", "samantha", "victoria", "karen")
                    )
                ),
                None,
            )
            if female:
                engine.setProperty("voice", female.id)
            self._pyttsx3_engine = engine
            self._active_engine = "pyttsx3"
            print("[TTS] pyttsx3 ready (last-resort fallback) ✓")
            print("[TTS] ⚠  pyttsx3 uses your system voice — no voice diversity.")
            print("[TTS]    For neural voices: pip install edge-tts")
        except ImportError:
            print("[TTS] pyttsx3 not installed — speech disabled.")
        except Exception as exc:
            print(f"[TTS] pyttsx3 init failed: {exc} — speech disabled.")

    def _speak_pyttsx3(self, text: str):
        try:
            self._pyttsx3_engine.say(text)
            self._pyttsx3_engine.runAndWait()
        except RuntimeError as exc:
            if config.DEBUG:
                print(f"[TTS] pyttsx3 RuntimeError (ignored): {exc}")
        except Exception as exc:
            if config.DEBUG:
                print(f"[TTS] pyttsx3 speak error: {exc}")

    # ── Public: speak ──────────────────────────────────────────────────────────
    def speak(self, text: str):
        """Thread-safe synthesis + playback (called via asyncio.to_thread)."""
        if not text or self._active_engine == "none":
            return
        with self._lock:
            if self._active_engine == "edge":
                self._speak_edge(text)
            elif self._active_engine == "piper" and self._piper_voice:
                self._speak_piper(text)
            elif self._active_engine == "pyttsx3" and self._pyttsx3_engine:
                self._speak_pyttsx3(text)

    # ── Public: voice management ───────────────────────────────────────────────
    def switch_voice(self, voice_key: str) -> str:
        resolved = VOICE_ALIASES.get(voice_key.lower(), voice_key.lower())

        if self._active_engine == "none":
            return (
                "TTS is currently disabled (TTS_ENGINE=none). "
                "Set TTS_ENGINE=edge in your .env and configure audio passthrough "
                "in docker-compose.yml to enable voice switching."
            )

        if self._active_engine == "edge":
            info = EDGE_VOICES.get(resolved)
            if not info:
                # Accept raw edge names like "en-US-EmmaNeural"
                if voice_key.startswith("en-") and "-" in voice_key:
                    self._edge_voice_name = voice_key
                    self._current_voice = voice_key
                    return f"Voice switched to {voice_key}."
                avail = ", ".join(list(EDGE_VOICES.keys()) + list(VOICE_ALIASES.keys()))
                return f"Unknown voice '{voice_key}'. Available: {avail}"
            self._edge_voice_name = info["edge_name"]
            self._current_voice = resolved
            return f"Voice switched to {info['display']}."

        if self._active_engine == "piper":
            try:
                self._load_piper_voice(resolved)
                pk = self._resolve_piper_key(resolved)
                info = PIPER_VOICES.get(pk, {})
                return f"Voice switched to {info.get('display', resolved)}."
            except Exception as exc:
                return f"Could not load Piper voice '{voice_key}': {exc}"

        return (
            "Voice switching requires edge-tts or Piper TTS.\n"
            "Install edge-tts (recommended):  pip install edge-tts\n"
            "Install Piper (offline):          pip install piper-tts sounddevice"
        )

    def list_voices(self) -> str:
        if self._active_engine == "none":
            return (
                "TTS is currently disabled (TTS_ENGINE=none).\n"
                "Set TTS_ENGINE=edge in your .env and configure audio passthrough\n"
                "in docker-compose.yml to enable voices."
            )
        if self._active_engine == "edge":
            lines = ["Available edge-tts voices (say 'switch voice to <name>'):"]
            for key, info in EDGE_VOICES.items():
                marker = "  ✓ current" if key == self._current_voice else ""
                lines.append(f"  • {key:10s} — {info['display']}{marker}")
            lines.append(
                "\nAliases: male→guy  female→aria  british/uk→ryan  "
                "australian/au→natasha  indian→neerja"
            )
            lines.append("\nActive engine: edge-tts (neural, requires internet)")
        elif self._active_engine == "piper":
            lines = ["Available Piper voices (offline neural):"]
            for key, info in PIPER_VOICES.items():
                marker = "  ✓ current" if key == self._current_voice else ""
                lines.append(f"  • {key:10s} — {info['display']}{marker}")
            lines.append("\nActive engine: piper-tts (neural, fully offline)")
        else:
            lines = [
                f"Active engine: {self._active_engine}",
                "Diverse voices not available. Install: pip install edge-tts",
            ]
        return "\n".join(lines)

    @property
    def engine_type(self) -> str:
        return self._active_engine

    @property
    def current_voice(self) -> str:
        return self._current_voice
