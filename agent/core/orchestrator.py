"""
core/orchestrator.py — Async central controller for Samantha.

How the Tauri desktop connects to this process
───────────────────────────────────────────────
  invoke("start_backend")              Tauri spawns this as a sidecar
  GET  /health                         health check on every port change
  GET  /api/status                     agent state + model info
  GET  /api/history                    SQLite conversation history
  POST /api/chat  {"text": "..."}      typed messages from overlay / main chat
  WS   /ws/events                      real-time transcript + state stream

Typed messages (POST /api/chat) are pumped by _pump_chat_queue() into the
same self._stt.feed() queue as Rust-transcribed spoken utterances, so the
agent processes them identically — no separate code path.
"""
from __future__ import annotations

import asyncio
from typing import Optional

from rich.console import Console
from rich.live    import Live
from rich.panel   import Panel
from rich.spinner import Spinner
from rich.text    import Text

import config
from core.context import Context
from core.memory  import Memory
from core.planner import Planner
from core.schemas import ActionType, Plan, Action

console = Console()


class Orchestrator:
    def __init__(self):
        self.memory  = Memory()
        self.context = Context()
        self.planner = Planner()

        self._tts:            Optional[object] = None
        self._stt:            Optional[object] = None
        self._bridge:         Optional[object] = None
        self._browser:        Optional[object] = None
        self._wiki:           Optional[object] = None
        self._os:             Optional[object] = None
        self._gmail:          Optional[object] = None
        self._bridge_task:    Optional[asyncio.Task] = None
        self._api_task:       Optional[asyncio.Task] = None
        self._chat_pump_task: Optional[asyncio.Task] = None  # ← pumps POST /api/chat

    async def setup(self):
        from voice_io.tts import TTS
        self._tts = TTS()
        await self._tts.setup()

        from voice_io.stt import STT
        self._stt = STT()

        from tools.wikipedia  import WikipediaTool
        from tools.os_control import OSControl
        from tools.browser    import BrowserTool
        from tools.gmail      import GmailTool
        self._wiki    = WikipediaTool()
        self._os      = OSControl()
        self._browser = BrowserTool()
        self._gmail   = GmailTool(self._browser)

        # ── Rust audio bridge ────────────────────────────────────────────────
        if self._stt.mode == "rust_bridge":
            from voice_io.audio_bridge import AudioBridge
            self._bridge = AudioBridge(self._stt.model)
            try:
                await self._bridge.connect(retries=5, delay=1.0)
                self._stt.set_bridge(self._bridge)
                self._bridge_task = asyncio.create_task(
                    self._pump_bridge(), name="audio-bridge"
                )
                console.print("[dim][Orchestrator] Rust audio bridge active ✓[/dim]")
            except RuntimeError as e:
                console.print(f"[yellow]⚠  {e}  →  falling back to Python voice[/yellow]")
                import os as _os; _os.environ["STT_MODE"] = "voice"
                self._stt = STT()

        # ── API server (FastAPI + WebSocket for Tauri desktop) ────────────────
        if config.API_ENABLED:
            from api.server import run_server
            self._api_task = asyncio.create_task(
                run_server(self.memory), name="api-server"
            )
            # Pump POST /api/chat → STT feed queue (same path as spoken input)
            self._chat_pump_task = asyncio.create_task(
                self._pump_chat_queue(), name="chat-pump"
            )

        ok = await self.planner.health_check()
        if not ok:
            console.print(
                f"\n[bold yellow]⚠  Ollama model not ready.[/bold yellow]\n"
                f"  Run:  [cyan]ollama serve[/cyan]\n"
                f"  Then: [cyan]ollama pull {config.OLLAMA_MODEL}[/cyan]\n"
            )

        engine   = self._tts.engine_type
        voice    = self._tts.current_voice
        tts_info = {"edge": f"edge-tts ({voice})", "piper": f"piper ({voice})",
                    "pyttsx3": "pyttsx3", "none": "silent"}.get(engine, engine)
        stt_label = {"rust_bridge": "faster-whisper ← Rust engine",
                     "voice": "faster-whisper (Python)",
                     "text": "keyboard"}.get(self._stt.mode, self._stt.mode)

        console.print(Panel.fit(
            f"[bold magenta]{config.AGENT_NAME}:[/bold magenta] {config.GREETING}\n"
            f"[dim]TTS: {tts_info}  |  STT: {stt_label}\n"
            f"LLM: {config.OLLAMA_MODEL}  |  API: http://127.0.0.1:{config.API_PORT}[/dim]",
            border_style="magenta",
        ))
        await self._speak(config.GREETING)

    async def teardown(self):
        for task in [self._bridge_task, self._api_task, self._chat_pump_task]:
            if task:
                task.cancel()
        if self._bridge:
            await self._bridge.close()
        if self._browser:
            await self._browser.teardown()
        if self._tts:
            await self._tts.teardown()
        await self.planner.close()

    # ── Internal pumps ────────────────────────────────────────────────────────

    async def _pump_bridge(self):
        """Forward Rust audio engine utterances → STT feed queue."""
        assert self._bridge is not None
        async for transcript in self._bridge.utterances():
            if transcript:
                self._stt.feed(transcript)

    async def _pump_chat_queue(self):
        """
        Drain POST /api/chat messages and feed them into self._stt.feed().

        This gives the Tauri overlay bar and main chat view full text-input
        capability. Typed messages follow the exact same orchestration path
        as spoken utterances — no duplicate logic anywhere.
        """
        try:
            from api.server import get_chat_queue
            q = get_chat_queue()
        except ImportError:
            return

        while True:
            try:
                msg = await asyncio.wait_for(q.get(), timeout=1.0)
                text = msg.get("text", "").strip()
                if text and self._stt is not None:
                    self._stt.feed(text)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    # ── Main conversation loop ────────────────────────────────────────────────

    async def run_loop(self):
        try:
            from api.server import publish
        except ImportError:
            def publish(_): pass

        while True:
            publish({"type": "status", "state": "listening"})
            user_input = await self._listen()
            if not user_input:
                continue

            if user_input.lower().strip() in ("exit", "quit", "bye", "goodbye", "stop"):
                farewell = "Goodbye! It was great talking with you."
                console.print(f"[bold magenta]{config.AGENT_NAME}:[/bold magenta] {farewell}")
                publish({"type": "transcript", "role": "assistant", "text": farewell})
                await self._speak(farewell)
                break

            console.print(f"\n[bold cyan]You:[/bold cyan] {user_input}")
            publish({"type": "transcript", "role": "user", "text": user_input})

            publish({"type": "status", "state": "thinking"})
            plan = await self._think(user_input, self.memory.summary_context(5))

            if plan.confidence < config.MIN_CONFIDENCE:
                clarify = "I'm not quite sure what you mean. Could you give me a bit more detail?"
                console.print(f"[bold magenta]{config.AGENT_NAME}:[/bold magenta] {clarify}")
                publish({"type": "transcript", "role": "assistant", "text": clarify})
                await self._speak(clarify)
                publish({"type": "status", "state": "idle"})
                continue

            publish({"type": "status", "state": "acting",
                     "actions": [a.type.value for a in plan.actions]})
            agent_reply = await self._execute(plan, user_input)

            if agent_reply:
                console.print(f"\n[bold magenta]{config.AGENT_NAME}:[/bold magenta] {agent_reply}\n")
                publish({"type": "transcript", "role": "assistant", "text": agent_reply})
                publish({"type": "status", "state": "speaking"})
                await self._speak(agent_reply)

            self.context.add("user",      user_input)
            self.context.add("assistant", agent_reply or "")
            self.memory.save(user=user_input, agent=agent_reply or "")
            publish({"type": "status", "state": "idle"})  # ← reset UI after each turn

    # ── Private helpers ───────────────────────────────────────────────────────

    async def _think(self, user_input: str, memory_ctx: str) -> Plan:
        result: list[Plan] = []
        async def _do():
            result.append(await self.planner.plan(
                user_input=user_input,
                context=self.context.messages(),
                memory_context=memory_ctx,
            ))
        with Live(Spinner("dots3", text=Text("  Samantha is thinking…", style="bold magenta")),
                  refresh_per_second=10, transient=True, console=console):
            await _do()
        return result[0]

    async def _execute(self, plan: Plan, user_input: str) -> str:
        results = []
        for action in plan.actions:
            console.print(f"  [yellow]→ [{action.type.value}][/yellow] {action.description}")
            for attempt in range(1, config.MAX_ACTION_RETRIES + 1):
                try:
                    result = await self._run_action(action, user_input)
                    if result:
                        results.append(result)
                    break
                except Exception as exc:
                    if attempt == config.MAX_ACTION_RETRIES:
                        msg = f"Action '{action.type.value}' failed: {exc}"
                        console.print(f"  [red]✗ {msg}[/red]")
                        results.append(msg)
                    else:
                        await asyncio.sleep(0.5 * attempt)
        return "\n".join(results) if results else "Done."

    async def _run_action(self, action: Action, user_input: str):
        p = action.params
        match action.type:
            case ActionType.CONVERSE:     return p.get("response", "")
            case ActionType.RECALL:
                turns = self.memory.recent(5)
                if not turns: return "No stored history yet."
                return "Here's what I remember:\n" + "\n".join(
                    f"• {t['ts'][:16]}  You: {t['user'][:70]}  →  Me: {t['agent'][:70]}"
                    for t in turns)
            case ActionType.WIKIPEDIA:    return await asyncio.to_thread(self._wiki.search, p.get("query", user_input))
            case ActionType.BROWSE:
                if not p.get("url"): return "No URL provided."
                await self._ensure_browser(); return await self._browser.navigate(p["url"])
            case ActionType.SMART_BROWSE:
                if not p.get("site"): return "No site name provided."
                await self._ensure_browser(); return await self._browser.smart_navigate(p["site"])
            case ActionType.SEARCH_WEB:
                await self._ensure_browser(); return await self._browser.google_search(p.get("query", user_input))
            case ActionType.YOUTUBE_OPEN:   await self._ensure_browser(); return await self._browser.youtube_open()
            case ActionType.YOUTUBE_SEARCH: await self._ensure_browser(); return await self._browser.youtube_search(p.get("query", user_input))
            case ActionType.YOUTUBE_PLAY:   await self._ensure_browser(); return await self._browser.youtube_play(p.get("query", user_input))
            case ActionType.OPEN_APP:
                if not p.get("app"): return "No app specified."
                return self._os.open_app(p["app"])
            case ActionType.HOTKEY:
                if not p.get("keys"): return "No hotkey specified."
                return self._os.hotkey(p["keys"])
            case ActionType.SCREENSHOT:   return self._os.screenshot()
            case ActionType.TYPE_TEXT:
                if not p.get("text"): return "No text to type."
                return self._os.type_text(p["text"])
            case ActionType.SEND_EMAIL:
                await self._ensure_browser()
                return await self._gmail.send(
                    to=p.get("to", ""), subject=p.get("subject", "(no subject)"), body=p.get("body", ""))
            case ActionType.SWITCH_VOICE:
                if not p.get("voice"): return "No voice name provided."
                return await asyncio.to_thread(self._tts.switch_voice, p["voice"])
            case ActionType.LIST_VOICES:  return self._tts.list_voices()
            case _:                        return f"Unknown action: {action.type}"

    async def _ensure_browser(self):
        if not self._browser.is_open:
            await self._browser.setup()

    async def _listen(self) -> str:
        try:
            if self._stt.mode == "text":
                console.print("[bold green]▶[/bold green] ", end="")
            return (await asyncio.get_event_loop().run_in_executor(None, self._stt.listen) or "").strip()
        except Exception as exc:
            if config.DEBUG: console.print(f"[red][STT error][/red] {exc}")
            return ""

    async def _speak(self, text: str):
        if not text: return
        try:
            await asyncio.to_thread(self._tts.speak, text)
        except Exception as exc:
            if config.DEBUG: console.print(f"[red][TTS error][/red] {exc}")
