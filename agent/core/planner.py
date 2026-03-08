"""
core/planner.py — Async LLM planner backed by Ollama (100% free, runs locally).

Speed improvements:
  • Streaming accumulation — first token arrives faster.
  • num_ctx=2048, num_predict=512, temperature=0.1.
  • Default model: llama3.2:3b (~3× faster than deepseek-r1:7b).
    Set OLLAMA_MODEL=deepseek-r1:7b in .env for heavier reasoning.

Screen actions (read_screen / find_element / click_element) are only emitted
when the user explicitly asks about screen content. The planner never adds them
speculatively — always on direct user request.
"""
from __future__ import annotations

import asyncio
import json
import re
import subprocess
import time
from typing import List

import httpx

import config
from core.schemas import Action, ActionType, Plan

# ── System prompt ─────────────────────────────────────────────────────────────
SYSTEM_PROMPT = """\
You are Samantha, an intelligent AI desktop assistant.
Analyse the user's request and return ONLY a valid JSON execution plan.
Do NOT include any text, explanation, markdown, or <think> tags outside the JSON.

Available action types and their required params:
  browse          → {"url": "https://..."}
  smart_browse    → {"site": "youtube"}            (resolves name to URL automatically)
  search_web      → {"query": "..."}               (Google search)
  youtube_open    → {}                             (open YouTube homepage)
  youtube_search  → {"query": "..."}              (search YouTube for query)
  youtube_play    → {"query": "..."}              (search YouTube and auto-play first)
  wikipedia       → {"query": "..."}
  open_app        → {"app": "Spotify"}
  send_email      → {"to": "...", "subject": "...", "body": "..."}
  converse        → {"response": "your full answer here"}
  recall          → {}
  hotkey          → {"keys": "ctrl+c"}
  screenshot      → {}
  type_text       → {"text": "..."}
  read_screen     → {}                             (capture + OCR + element detection; describe what is on screen)
  find_element    → {"label": "Submit"}            (locate a named button, field, or icon on screen)
  click_element   → {"label": "Submit"}            (find and click a UI element by its label)
  switch_voice    → {"voice": "guy"}              (aria, jenny, guy, davis, ryan, sonia, natasha, william, neerja, prabhat)
  list_voices     → {}

Return exactly this JSON (no extra keys, no markdown fences, no prose):
{
  "actions": [
    {"type": "<action_type>", "description": "<why>", "params": {<key>: <value>}}
  ],
  "confidence": 0.95,
  "reasoning": "<one short sentence>"
}

Rules:
1. Output ONLY the JSON object — nothing before or after it.
2. For pure questions or chat → use "converse" with full answer in params.response.
3. For "open youtube" → use youtube_open.
4. For "search youtube for cats" → use youtube_search {"query": "cats"}.
5. For "play lo-fi music on youtube" → use youtube_play {"query": "lo-fi music"}.
6. For common websites by name (reddit, twitter/X, gmail, maps) → use smart_browse.
7. Use multiple actions for sequential steps.
8. confidence is a float 0.0–1.0.
9. Never leave params as {} unless the action genuinely needs no parameters.
10. Strip any <think>…</think> reasoning from your output — return ONLY JSON.
11. Use read_screen ONLY when the user explicitly asks what is on the screen,
    to read or summarise on-screen content, or to verify something visually.
12. Use find_element when the user asks where a specific button/field/icon is.
13. Use click_element when the user says "click", "press", or "tap" a named element.
14. For sequential screen tasks, chain actions: e.g. find_element then click_element.
"""


def _extract_json(text: str) -> dict:
    """
    Robustly extract the first JSON object from a model response.
    Handles deepseek-r1 <think>…</think> tags and markdown fences.
    """
    text = re.sub(r"<think>.*?</think>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"```(?:json)?", "", text, flags=re.IGNORECASE).strip()
    start = text.find("{")
    end   = text.rfind("}") + 1
    if start == -1 or end <= 0:
        raise ValueError(f"No JSON object found in:\n{text[:400]}")
    return json.loads(text[start:end])


def _fallback(msg: str = "") -> Plan:
    reply = msg or "I had trouble processing that. Could you rephrase your request?"
    return Plan(
        actions=[Action(
            type=ActionType.CONVERSE,
            description="Fallback — parse error",
            params={"response": reply},
        )],
        confidence=0.4,
        reasoning="JSON parse failure — using fallback",
    )


class Planner:
    def __init__(self):
        self._client = httpx.AsyncClient(
            base_url=config.OLLAMA_HOST,
            timeout=config.OLLAMA_TIMEOUT,
        )
        self._ollama_started = False

    # ── Main plan method ───────────────────────────────────────────────────────
    async def plan(
        self,
        user_input: str,
        context: list,
        memory_context: str = "",
    ) -> Plan:
        parts = []
        if memory_context.strip():
            parts.append(f"[Conversation history]\n{memory_context}\n")
        if context:
            history = "\n".join(
                ("User" if m["role"] == "user" else "Samantha") + ": " + m["content"]
                for m in context[-6:]
            )
            parts.append(f"[Current session]\n{history}\n")
        parts.append(f"[New request]\n{user_input}")
        user_message = "\n".join(parts)

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": user_message},
        ]

        try:
            raw_text = await self._call_ollama_streaming(messages)
            if config.DEBUG:
                print(f"\n[Planner raw]\n{raw_text}\n")
            return self._build_plan(_extract_json(raw_text))

        except httpx.ConnectError:
            print(f"\n[Planner] ⚠  Cannot reach Ollama at {config.OLLAMA_HOST}.")
            if config.OLLAMA_AUTO_START:
                if await self._try_start_ollama():
                    try:
                        raw_text = await self._call_ollama_streaming(messages)
                        return self._build_plan(_extract_json(raw_text))
                    except Exception as exc2:
                        if config.DEBUG:
                            print(f"[Planner] Second attempt failed: {exc2}")
            print("[Planner] Trying subprocess fallback (ollama run)…")
            return await self._subprocess_plan(user_message)

        except json.JSONDecodeError as exc:
            if config.DEBUG:
                print(f"[Planner] JSON decode error: {exc}")
            return _fallback()

        except Exception as exc:
            if config.DEBUG:
                print(f"[Planner] Unexpected error: {exc}")
            return _fallback()

    # ── Ollama streaming call ─────────────────────────────────────────────────
    async def _call_ollama_streaming(self, messages: list) -> str:
        """
        Stream tokens from Ollama — lower perceived latency and avoids
        silent timeout on slower hardware.
        """
        chunks: list[str] = []

        async with self._client.stream(
            "POST",
            "/api/chat",
            json={
                "model":    config.OLLAMA_MODEL,
                "messages": messages,
                "stream":   True,
                "options": {
                    "temperature": config.LLM_TEMPERATURE,
                    "num_predict": config.LLM_MAX_TOKENS,
                    "num_ctx":     config.LLM_NUM_CTX,
                },
            },
        ) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except json.JSONDecodeError:
                    continue
                token = obj.get("message", {}).get("content", "")
                if token:
                    chunks.append(token)
                if obj.get("done"):
                    break

        return "".join(chunks).strip()

    # ── Auto-start Ollama ──────────────────────────────────────────────────────
    async def _try_start_ollama(self) -> bool:
        print("[Planner] Attempting to auto-start Ollama…")
        try:
            subprocess.Popen(
                ["ollama", "serve"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            for _ in range(6):
                await asyncio.sleep(1)
                if await self.health_check():
                    print("[Planner] Ollama auto-started ✓")
                    self._ollama_started = True
                    return True
            print("[Planner] Ollama did not start in time.")
            return False
        except FileNotFoundError:
            print("[Planner] 'ollama' not found on PATH.")
            return False
        except Exception as exc:
            print(f"[Planner] Could not start Ollama: {exc}")
            return False

    # ── Subprocess fallback ────────────────────────────────────────────────────
    async def _subprocess_plan(self, user_message: str) -> Plan:
        prompt = f"{SYSTEM_PROMPT}\n\n{user_message}"
        try:
            result = await asyncio.to_thread(
                subprocess.run,
                ["ollama", "run", config.OLLAMA_MODEL],
                input=prompt,
                capture_output=True,
                text=True,
                timeout=90,
            )
            raw = result.stdout.strip()
            if config.DEBUG:
                print(f"[Planner subprocess]\n{raw}\n")
            if raw:
                return self._build_plan(_extract_json(raw))
        except FileNotFoundError:
            pass
        except Exception as exc:
            if config.DEBUG:
                print(f"[Planner] Subprocess fallback error: {exc}")

        return _fallback(
            "I'm having trouble reaching my language model. "
            "Please ensure Ollama is installed and run: ollama serve"
        )

    # ── Build Plan ─────────────────────────────────────────────────────────────
    def _build_plan(self, data: dict) -> Plan:
        raw_actions = data.get("actions", [])
        if not raw_actions:
            return _fallback()

        actions: List[Action] = []
        for a in raw_actions:
            action_type = a.get("type", "converse").lower().strip().replace(" ", "_")
            actions.append(Action(
                type=action_type,
                description=a.get("description", ""),
                params=a.get("params", {}),
            ))

        return Plan(
            actions=actions,
            confidence=float(data.get("confidence", 0.8)),
            reasoning=data.get("reasoning", ""),
        )

    # ── Utility ────────────────────────────────────────────────────────────────
    async def health_check(self) -> bool:
        try:
            r = await self._client.get("/api/tags", timeout=5)
            r.raise_for_status()
            models     = [m["name"] for m in r.json().get("models", [])]
            model_base = config.OLLAMA_MODEL.split(":")[0]
            available  = any(model_base in m for m in models)
            if not available:
                print(
                    f"[Planner] Model '{config.OLLAMA_MODEL}' not found in Ollama.\n"
                    f"  Available: {models}\n"
                    f"  Pull it:   ollama pull {config.OLLAMA_MODEL}"
                )
            return available
        except Exception:
            return False

    async def close(self):
        await self._client.aclose()
