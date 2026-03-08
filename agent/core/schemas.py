"""
core/schemas.py — Pydantic data contracts shared across all modules.
"""
from __future__ import annotations
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class ActionType(str, Enum):
    # ── Navigation ────────────────────────────────────────────────────
    BROWSE         = "browse"          # navigate to a URL
    SMART_BROWSE   = "smart_browse"    # smart name → URL ("youtube", "gmail" …)
    SEARCH_WEB     = "search_web"      # Google search via browser
    # ── YouTube ──────────────────────────────────────────────────────
    YOUTUBE_OPEN   = "youtube_open"    # open youtube.com homepage
    YOUTUBE_SEARCH = "youtube_search"  # search YouTube for a query
    YOUTUBE_PLAY   = "youtube_play"    # search and auto-play first result
    # ── Knowledge ─────────────────────────────────────────────────────
    WIKIPEDIA      = "wikipedia"       # Wikipedia article lookup
    # ── Desktop OS ────────────────────────────────────────────────────
    OPEN_APP       = "open_app"        # launch a desktop application
    HOTKEY         = "hotkey"          # send a keyboard shortcut
    SCREENSHOT     = "screenshot"      # basic screenshot save (pyautogui)
    TYPE_TEXT      = "type_text"       # type text at current cursor position
    # ── Screen vision (MSS + OpenCV + YOLOv8 + OCR) ──────────────────
    READ_SCREEN    = "read_screen"     # capture + OCR + element detection → describe
    FIND_ELEMENT   = "find_element"    # locate a named UI element, return coords
    CLICK_ELEMENT  = "click_element"   # find element and click it
    # ── Communication ────────────────────────────────────────────────
    SEND_EMAIL     = "send_email"      # compose & send via Gmail web
    # ── Conversation ─────────────────────────────────────────────────
    CONVERSE       = "converse"        # pure conversation / answer
    RECALL         = "recall"          # retrieve conversation memory
    # ── Voice control ────────────────────────────────────────────────
    SWITCH_VOICE   = "switch_voice"    # switch TTS voice
    LIST_VOICES    = "list_voices"     # list available TTS voices


class Action(BaseModel):
    type: ActionType
    description: str = ""
    params: Dict[str, Any] = Field(default_factory=dict)
    # Per-type expected params:
    # BROWSE          {"url": "https://..."}
    # SMART_BROWSE    {"site": "youtube"}
    # SEARCH_WEB      {"query": "..."}
    # YOUTUBE_OPEN    {}
    # YOUTUBE_SEARCH  {"query": "..."}
    # YOUTUBE_PLAY    {"query": "..."}
    # WIKIPEDIA       {"query": "..."}
    # OPEN_APP        {"app": "Spotify"}
    # SEND_EMAIL      {"to": "...", "subject": "...", "body": "..."}
    # CONVERSE        {"response": "..."}
    # RECALL          {}
    # HOTKEY          {"keys": "ctrl+c"}
    # SCREENSHOT      {}
    # TYPE_TEXT       {"text": "..."}
    # READ_SCREEN     {}   (optional: {"monitor": 1})
    # FIND_ELEMENT    {"label": "Submit"}
    # CLICK_ELEMENT   {"label": "Submit"}
    # SWITCH_VOICE    {"voice": "ryan"}
    # LIST_VOICES     {}


class Plan(BaseModel):
    actions: List[Action]
    confidence: float = Field(default=0.8, ge=0.0, le=1.0)
    reasoning: str = ""


class Turn(BaseModel):
    user: str
    agent: str
    ts: Optional[str] = None
