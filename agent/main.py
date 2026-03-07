"""
main.py — Entry point for Samantha AI v2.

Modes:
  python main.py              → rust_bridge mode (Rust audio + faster-whisper)
  python main.py --voice      → Python-only voice mode (sounddevice fallback)
  python main.py --text       → text/keyboard mode (no mic)
  python main.py --daemon     → headless mode for systemd (no TUI panels)
  python main.py --test       → smoke-test Ollama planner and exit
  python main.py --memory     → print conversation history and exit
  python main.py --clear      → wipe conversation memory and exit
  python main.py --models     → list available Ollama models and exit
  python main.py --voices     → list available TTS voices and exit

Architecture v2 changes:
  • STT: openai-whisper → faster-whisper (4× faster, CTranslate2)
  • Audio capture: Python SpeechRecognition → Rust audio engine (IPC)
  • New: FastAPI local API bridge on :7799 for frontend dashboard
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys


def _set_stt_mode(mode: str):
    os.environ["STT_MODE"] = mode


async def main(args: argparse.Namespace):
    from rich.console import Console
    from rich.panel import Panel

    console = Console()

    if not args.daemon:
        console.print(
            Panel.fit(
                "[bold magenta]✨  Samantha v2 — AI Voice Assistant[/bold magenta]\n"
                "[dim]faster-whisper · Ollama · Rust audio engine · edge-tts · Playwright[/dim]",
                border_style="magenta",
            )
        )

    # ── Utility modes ──────────────────────────────────────────────────────────
    if args.voices:
        from voice_io.tts import EDGE_VOICES, PIPER_VOICES

        console.print("\n[bold]Edge-TTS voices:[/bold]")
        for key, info in EDGE_VOICES.items():
            console.print(f"  • [cyan]{key:12s}[/cyan] {info['display']}")
        return

    if args.models:
        import config as cfg
        import httpx

        try:
            r = httpx.get(f"{cfg.OLLAMA_HOST}/api/tags", timeout=5)
            models = r.json().get("models", [])
            console.print("\n[bold]Available Ollama models:[/bold]")
            for m in models:
                tag = " ← active" if cfg.OLLAMA_MODEL in m["name"] else ""
                console.print(f"  • {m['name']}{tag}")
        except Exception as exc:
            console.print(f"[red]Cannot reach Ollama: {exc}[/red]")
        return

    if args.memory:
        from core.memory import Memory

        mem = Memory()
        console.print(f"\n[bold]Stored turns:[/bold] {mem.count()}\n")
        for t in mem.recent(10):
            console.print(f"[dim]{t['ts'][:16]}[/dim]")
            console.print(f"  [cyan]You:[/cyan]       {t['user'][:100]}")
            console.print(f"  [magenta]Samantha:[/magenta] {t['agent'][:120]}\n")
        return

    if args.clear:
        from core.memory import Memory

        Memory().clear()
        console.print("[green]✓ Memory cleared.[/green]")
        return

    if args.test:
        console.print("\n[yellow]Smoke-testing Ollama planner…[/yellow]\n")
        import config as cfg
        from core.planner import Planner

        planner = Planner()
        ok = await planner.health_check()
        if not ok:
            console.print(
                f"[red]⚠  Ollama health check failed.[/red]\n"
                f"  ollama serve && ollama pull {cfg.OLLAMA_MODEL}"
            )
            await planner.close()
            return
        for cmd in [
            "What is the capital of France?",
            "Open YouTube",
            "Play lo-fi music on YouTube",
            "Search Google for open-source AI",
            "Open Spotify",
            "Send an email to test@example.com about the meeting",
            "Take a screenshot",
        ]:
            console.print(f"[cyan]▶[/cyan] {cmd}")
            plan = await planner.plan(user_input=cmd, context=[], memory_context="")
            console.print(
                f"  [green]✓[/green] {len(plan.actions)} action(s)  "
                f"conf={plan.confidence:.0%}  {plan.reasoning}"
            )
            for i, a in enumerate(plan.actions, 1):
                console.print(f"    [{i}] {a.type.value} — {a.params}")
            console.print()
        await planner.close()
        return

    # ── Normal run ─────────────────────────────────────────────────────────────
    mode = os.environ.get("STT_MODE", "rust_bridge")
    if not args.daemon:
        labels = {
            "rust_bridge": "🦀 Rust engine + faster-whisper",
            "voice": "🐍 Python capture + faster-whisper",
            "text": "⌨️  Keyboard (text mode)",
        }
        console.print(f"[bold]Input:[/bold] {labels.get(mode, mode)}")
        if mode in ("rust_bridge", "voice"):
            console.print(
                "[dim]Speak your request. Say 'exit' or 'quit' to stop.[/dim]\n"
            )
        else:
            console.print(
                "[dim]Type your request and press Enter. Type 'exit' to stop.[/dim]\n"
            )

    from core.orchestrator import Orchestrator

    agent = Orchestrator()
    try:
        await agent.setup()
        await agent.run_loop()
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted (Ctrl+C).[/yellow]")
    finally:
        await agent.teardown()
        console.print("[dim]Samantha shut down. Goodbye![/dim]")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Samantha v2 — AI Voice Assistant")
    parser.add_argument("--voice", action="store_true", help="Python-only voice mode")
    parser.add_argument("--text", action="store_true", help="Keyboard text input")
    parser.add_argument(
        "--daemon", action="store_true", help="Headless daemon mode (systemd)"
    )
    parser.add_argument(
        "--test", action="store_true", help="Smoke-test planner and exit"
    )
    parser.add_argument(
        "--memory", action="store_true", help="Show conversation memory"
    )
    parser.add_argument(
        "--clear", action="store_true", help="Clear conversation memory"
    )
    parser.add_argument("--models", action="store_true", help="List Ollama models")
    parser.add_argument("--voices", action="store_true", help="List TTS voices")
    args = parser.parse_args()

    if args.text:
        _set_stt_mode("text")
    elif args.voice:
        _set_stt_mode("voice")
    # default: rust_bridge (from config / .env)

    asyncio.run(main(args))
