"""
tools/browser.py — Async Playwright browser automation with smart URL resolution.

Docker support:
  In DOCKER_MODE, Chromium is launched with --no-sandbox and --disable-dev-shm-usage
  to prevent crashes when running as root inside a container.
"""
from __future__ import annotations

import os
from typing import Optional
from urllib.parse import quote_plus

from playwright.async_api import (
    async_playwright,
    BrowserContext,
    Page,
    Playwright,
)

import config


# ── Common site name → URL resolver ───────────────────────────────────────────
SITE_MAP = {
    "youtube":        "https://www.youtube.com",
    "yt":             "https://www.youtube.com",
    "google":         "https://www.google.com",
    "gmail":          "https://mail.google.com",
    "email":          "https://mail.google.com",
    "mail":           "https://mail.google.com",
    "google maps":    "https://maps.google.com",
    "maps":           "https://maps.google.com",
    "google drive":   "https://drive.google.com",
    "drive":          "https://drive.google.com",
    "reddit":         "https://www.reddit.com",
    "twitter":        "https://www.twitter.com",
    "x":              "https://www.x.com",
    "instagram":      "https://www.instagram.com",
    "facebook":       "https://www.facebook.com",
    "github":         "https://www.github.com",
    "wikipedia":      "https://www.wikipedia.org",
    "netflix":        "https://www.netflix.com",
    "spotify":        "https://open.spotify.com",
    "twitch":         "https://www.twitch.tv",
    "amazon":         "https://www.amazon.com",
    "news":           "https://news.google.com",
    "weather":        "https://weather.com",
    "stackoverflow":  "https://stackoverflow.com",
    "stack overflow": "https://stackoverflow.com",
    "chatgpt":        "https://chat.openai.com",
    "claude":         "https://claude.ai",
}

# Extra Chromium flags required when running inside Docker (root, no sandbox)
_DOCKER_ARGS = [
    "--no-sandbox",
    "--disable-setuid-sandbox",
    "--disable-dev-shm-usage",
    "--disable-gpu",
]


class BrowserTool:
    def __init__(self):
        self._pw:      Optional[Playwright]     = None
        self._context: Optional[BrowserContext] = None
        self._page:    Optional[Page]           = None
        self.is_open:  bool                     = False

    # ── Lifecycle ──────────────────────────────────────────────────────────────
    async def setup(self):
        if self.is_open:
            return
        self._pw = await async_playwright().start()

        launch_args = ["--disable-blink-features=AutomationControlled"]
        if config.BROWSER_HEADLESS:
            # In headless mode maximised flag does nothing; skip it
            pass
        else:
            launch_args.append("--start-maximized")

        if config.DOCKER_MODE:
            launch_args.extend(_DOCKER_ARGS)

        self._context = await self._pw.chromium.launch_persistent_context(
            user_data_dir=config.BROWSER_PROFILE,
            headless=config.BROWSER_HEADLESS,
            slow_mo=config.BROWSER_SLOW_MO,
            args=launch_args,
        )
        pages = self._context.pages
        self._page = pages[0] if pages else await self._context.new_page()
        self._page.set_default_timeout(config.BROWSER_TIMEOUT)
        self.is_open = True
        mode = "headless" if config.BROWSER_HEADLESS else "GUI"
        print(f"[Browser] Chromium ready ✓  ({mode})")

    async def teardown(self):
        if self._context:
            try:
                await self._context.close()
            except Exception:
                pass
        if self._pw:
            try:
                await self._pw.stop()
            except Exception:
                pass
        self.is_open = False

    # ── Smart navigation ───────────────────────────────────────────────────────
    async def smart_navigate(self, site: str) -> str:
        key = site.lower().strip()
        url = SITE_MAP.get(key)
        if not url:
            for k, v in SITE_MAP.items():
                if k in key or key in k:
                    url = v
                    break
        if not url:
            url = site if site.startswith("http") else f"https://www.{site}.com"
        return await self.navigate(url)

    async def navigate(self, url: str) -> str:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        await self._page.goto(url, wait_until="domcontentloaded")
        title = await self._page.title()
        return f"Opened: {title}  ({url})"

    # ── YouTube ────────────────────────────────────────────────────────────────
    async def youtube_open(self) -> str:
        return await self.navigate("https://www.youtube.com")

    async def youtube_search(self, query: str) -> str:
        url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        await self._page.goto(url, wait_until="domcontentloaded")
        titles = await self._page.eval_on_selector_all(
            "ytd-video-renderer #video-title",
            "els => els.slice(0, 5).map(e => e.innerText.trim()).filter(Boolean)",
        )
        if not titles:
            return f"Opened YouTube search for: {query}"
        top = "\n".join(f"  • {t}" for t in titles[:5])
        return f"YouTube search results for '{query}':\n{top}"

    async def youtube_play(self, query: str) -> str:
        url = f"https://www.youtube.com/results?search_query={quote_plus(query)}"
        await self._page.goto(url, wait_until="domcontentloaded")
        try:
            first = await self._page.wait_for_selector(
                "ytd-video-renderer a#thumbnail", timeout=8_000
            )
            href = await first.get_attribute("href")
            if href:
                video_url = f"https://www.youtube.com{href}"
                await self._page.goto(video_url, wait_until="domcontentloaded")
                title = await self._page.title()
                return f"Playing on YouTube: {title}"
            return f"Found results for '{query}' but couldn't auto-play. Check the browser."
        except Exception:
            return f"Opened YouTube search for '{query}'. Select a video to play."

    # ── Google search ──────────────────────────────────────────────────────────
    async def google_search(self, query: str) -> str:
        url = f"https://www.google.com/search?q={quote_plus(query)}"
        await self._page.goto(url, wait_until="domcontentloaded")
        titles = await self._page.eval_on_selector_all(
            "h3",
            "els => els.slice(0, 5).map(e => e.innerText.trim()).filter(Boolean)",
        )
        if not titles:
            return f"Search completed for: {query}"
        return "Top results for '{}':\n{}".format(
            query, "\n".join(f"• {t}" for t in titles)
        )

    # ── Page helpers ───────────────────────────────────────────────────────────
    async def current_url(self) -> str:
        return self._page.url if self._page else ""

    async def get_text(self, selector: str = "body") -> str:
        try:
            return await self._page.inner_text(selector)
        except Exception:
            return ""

    async def click(self, selector: str):
        await self._page.click(selector)

    async def fill(self, selector: str, value: str):
        await self._page.fill(selector, value)

    async def wait_for(self, selector: str, timeout: int = 5_000):
        await self._page.wait_for_selector(selector, timeout=timeout)

    @property
    def page(self) -> Optional[Page]:
        return self._page
