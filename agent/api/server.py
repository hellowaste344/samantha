"""
agent/api/server.py — FastAPI bridge between the Python agent and the Tauri desktop.

Endpoints
─────────
  GET  /health                → liveness probe  (Tauri health-check button)
  GET  /api/status            → agent state + config
  GET  /api/history?n=        → last N conversation turns (SQLite)
  POST /api/chat              → typed message from Tauri overlay / chat bar → agent
  POST /api/listen/start      → voice button pressed → trigger STT capture
  POST /api/listen/stop       → voice button released → stop STT capture
  WS   /ws/events             → real-time event stream (transcript, status)

Architecture
────────────
  Tauri desktop  ←WS─────→  /ws/events     (state + transcript in real time)
  Tauri desktop  ←HTTP───→  /health  /api/status  /api/history
  Tauri overlay  ─POST───→  /api/chat       (typed messages injected as speech)
  Tauri overlay  ─POST───→  /api/listen/start|stop  (voice button)
  Python agent   ─publish()→ all WS clients  (called from orchestrator)

CORS origins registered
───────────────────────
  http://localhost:1420       Tauri vite dev server
  https://tauri.localhost     Tauri production (Linux / Windows)
  tauri://localhost           Tauri production (macOS)
  http://localhost:3000       Any local web dev server
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any, Optional

import config

try:
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn
    _AVAILABLE = True
except ImportError:
    _AVAILABLE = False

# ── Shared state ──────────────────────────────────────────────────────────────

_subscribers: list[asyncio.Queue] = []

# Queue for typed messages from POST /api/chat and control signals from voice button.
_chat_queue: asyncio.Queue = asyncio.Queue(maxsize=64)

# Reference to the orchestrator — set by orchestrator.setup() via set_orchestrator()
_orchestrator: Optional[Any] = None


def set_orchestrator(orch: Any):
    """Called by Orchestrator.setup() to give the server a back-reference."""
    global _orchestrator
    _orchestrator = orch


def publish(event: dict[str, Any]):
    """Broadcast an event dict to every connected WebSocket client."""
    for q in list(_subscribers):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            pass  # slow client — drop frame


def get_chat_queue() -> asyncio.Queue:
    """Return the queue that POST /api/chat deposits messages into."""
    return _chat_queue


def _make_app(memory) -> "FastAPI":
    app = FastAPI(title="Samantha Local API", version="2.0.0")

    # ── CORS ─────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:1420",
            "http://localhost:3000",
            "https://tauri.localhost",
            "tauri://localhost",
            f"https://{config.DOMAIN}",
            "*",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── REST ──────────────────────────────────────────────────────────────────

    @app.get("/health")
    async def health():
        return {"ok": True, "ts": time.time()}

    @app.get("/api/status")
    async def status():
        return {
            "agent":      config.AGENT_NAME,
            "state":      "idle",
            "stt_mode":   config.STT_MODE,
            "tts_engine": config.TTS_ENGINE,
            "llm_model":  config.OLLAMA_MODEL,
            "domain":     config.DOMAIN,
            "uptime":     time.time(),
        }

    @app.get("/api/history")
    async def history(n: int = 20):
        turns = memory.recent(n)
        return {"turns": turns, "total": memory.count()}

    # ── POST /api/chat ────────────────────────────────────────────────────────

    @app.post("/api/chat")
    async def chat(request: Request):
     try:
        body = await request.json()
        text = (body.get("text") or "").strip()
     except Exception:
        return {"ok": False, "error": "invalid JSON body"}

     if not text:
        return {"ok": False, "error": "empty message"}
     try:
        _chat_queue.put_nowait({"text": text, "ts": time.time()})
        return {"ok": True}
     except asyncio.QueueFull:
        return {"ok": False, "error": "agent busy — try again shortly"}

    # ── POST /api/listen/start ────────────────────────────────────────────────
    # Called when the user presses the voice button in the Tauri UI.
    # Signals the orchestrator to start a single STT capture turn.

    @app.post("/api/listen/start")
    async def listen_start():
        if _orchestrator is None:
            return {"ok": False, "error": "agent not ready"}

        # Check if already listening
        if _orchestrator._listen_lock.locked():
            return {"ok": False, "error": "already listening"}

        try:
            _chat_queue.put_nowait({
                "text":    "__listen_start__",
                "ts":      time.time(),
                "control": True,
            })
            publish({"type": "status", "state": "listening"})
            return {"ok": True}
        except asyncio.QueueFull:
            return {"ok": False, "error": "agent busy"}

    # ── POST /api/listen/stop ─────────────────────────────────────────────────
    # Called when the user presses the voice button again to cancel.
    # Note: STT capture is blocking — this signals intent but the current
    # capture will finish naturally. For immediate cancel, implement
    # interrupt support in your STT class.

    @app.post("/api/listen/stop")
    async def listen_stop():
        try:
            _chat_queue.put_nowait({
                "text":    "__listen_stop__",
                "ts":      time.time(),
                "control": True,
            })
            publish({"type": "status", "state": "idle"})
            return {"ok": True}
        except asyncio.QueueFull:
            return {"ok": False, "error": "queue full"}

    # ── WebSocket /ws/events ──────────────────────────────────────────────────

    @app.websocket("/ws/events")
    async def ws_events(ws: WebSocket):
        await ws.accept()
        q: asyncio.Queue = asyncio.Queue(maxsize=64)
        _subscribers.append(q)

        # Send current state immediately on connect
        publish({"type": "status", "state": "idle"})

        try:
            while True:
                event = await q.get()
                await ws.send_text(json.dumps(event))
        except (WebSocketDisconnect, Exception):
            pass
        finally:
            if q in _subscribers:
                _subscribers.remove(q)

    return app


async def run_server(memory):
    """Start the API server as an asyncio background task."""
    if not _AVAILABLE:
        print(
            "[API] FastAPI / uvicorn not installed — Tauri bridge disabled.\n"
            "      pip install fastapi uvicorn[standard]"
        )
        return

    app = _make_app(memory)
    cfg = uvicorn.Config(
        app,
        host      = "127.0.0.1",
        port      = config.API_PORT,
        log_level = "warning",
        loop      = "asyncio",
    )
    server = uvicorn.Server(cfg)
    print(f"[API] Tauri bridge → http://127.0.0.1:{config.API_PORT}")
    await server.serve()