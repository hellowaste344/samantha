"""
voice_io/windows_mic_bridge.py

Mic capture for WSL. Run via Windows Python (spawned automatically by
`make backend` — never needs to be started manually).

Captures audio through WASAPI, applies WebRTC VAD, and streams the same
newline-delimited JSON protocol as the Rust engine over TCP so
audio_bridge.py needs no changes.

Protocol:
  {"type":"speech_start","sample_rate":16000}
  {"type":"audio_chunk","data":"<base64 f32-le>","n_samples":N}
  {"type":"speech_end","duration_ms":1250}
  {"type":"ping"}
"""

import base64
import json
import os
import socket
import sys
import threading
import time

try:
    import numpy as np
    import sounddevice as sd
    import webrtcvad
except ImportError:
    sys.stderr.write(
        "[windows_mic_bridge] Missing deps — install on Windows Python:\n"
        "  pip install sounddevice webrtcvad numpy\n"
    )
    sys.exit(1)

SAMPLE_RATE   = 16_000
FRAME_MS      = 20
FRAME_SAMPLES = SAMPLE_RATE * FRAME_MS // 1000  # 320
PING_INTERVAL = 5.0


def run(port: int = 9876, vad_level: int = 2,
        silence_ms: int = 600, min_speech_ms: int = 200):

    silence_frames    = silence_ms    // FRAME_MS
    min_speech_frames = min_speech_ms // FRAME_MS

    vad = webrtcvad.Vad(vad_level)

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    # Bind to loopback only — the WSL agent connects over 127.0.0.1 and there
    # is no reason to expose the raw microphone stream on external interfaces.
    srv.bind(("127.0.0.1", port))
    srv.listen(1)
    sys.stdout.write(f"[windows_mic_bridge] listening on port {port}\n")
    sys.stdout.flush()

    while True:
        conn, _ = srv.accept()
        sys.stdout.write("[windows_mic_bridge] agent connected\n")
        sys.stdout.flush()

        frame_q: list = []
        lock     = threading.Lock()
        stop_evt = threading.Event()

        def audio_cb(indata, frames, time_info, status):
            with lock:
                frame_q.append(indata[:, 0].copy())

        def send(obj: dict):
            try:
                conn.sendall((json.dumps(obj) + "\n").encode())
            except (BrokenPipeError, ConnectionResetError, OSError):
                stop_evt.set()

        def ping_loop():
            while not stop_evt.is_set():
                time.sleep(PING_INTERVAL)
                if not stop_evt.is_set():
                    send({"type": "ping"})

        stream = sd.InputStream(
            samplerate=SAMPLE_RATE, channels=1,
            dtype="float32", blocksize=FRAME_SAMPLES,
            callback=audio_cb,
        )
        threading.Thread(target=ping_loop, daemon=True).start()

        state = "idle"
        silence_count = speech_frames = 0
        speech_buf: list = []
        flush_buf:  list = []
        FLUSH_SAMPLES = SAMPLE_RATE // 1000 * 400  # 400 ms

        with stream:
            while not stop_evt.is_set():
                time.sleep(0.005)
                with lock:
                    frames, frame_q[:] = frame_q[:], []

                for frame in frames:
                    i16 = (frame * 32767).clip(-32768, 32767).astype("int16")
                    is_speech = vad.is_speech(i16.tobytes(), SAMPLE_RATE)

                    if state == "idle":
                        if is_speech:
                            state = "speaking"
                            silence_count = 0
                            speech_frames = 1
                            speech_buf = [frame]
                            flush_buf  = [frame]
                            send({"type": "speech_start", "sample_rate": SAMPLE_RATE})

                    else:
                        speech_buf.append(frame)
                        flush_buf.append(frame)
                        silence_count = 0 if is_speech else silence_count + 1
                        if is_speech:
                            speech_frames += 1

                        if sum(f.shape[0] for f in flush_buf) >= FLUSH_SAMPLES:
                            chunk = np.concatenate(flush_buf)
                            b64   = base64.b64encode(chunk.astype("float32").tobytes()).decode()
                            send({"type": "audio_chunk", "data": b64, "n_samples": len(chunk)})
                            flush_buf = []

                        if silence_count >= silence_frames:
                            if speech_frames >= min_speech_frames:
                                if flush_buf:
                                    chunk = np.concatenate(flush_buf)
                                    b64   = base64.b64encode(chunk.astype("float32").tobytes()).decode()
                                    send({"type": "audio_chunk", "data": b64, "n_samples": len(chunk)})
                                send({"type": "speech_end",
                                      "duration_ms": speech_frames * FRAME_MS})
                            state = "idle"
                            silence_count = speech_frames = 0
                            speech_buf = []
                            flush_buf  = []

        conn.close()
        stop_evt.clear()


if __name__ == "__main__":
    # Spawned by Makefile: python windows_mic_bridge.py <port>
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9876
    run(port=port)
