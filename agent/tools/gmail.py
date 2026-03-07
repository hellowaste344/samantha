"""
tools/gmail.py — Gmail compose & send via Playwright (no Gmail API key needed).

Works with the persistent browser profile — log in once, stays logged in.
First run: the browser will open gmail.com and prompt for Google login.
Subsequent runs: session cookie is reused automatically.
"""
from __future__ import annotations
import asyncio

import config


class GmailTool:
    _GMAIL         = "https://mail.google.com"
    _COMPOSE       = "[gh='cm']"
    _TO            = "textarea[name='to']"
    _SUBJECT       = "input[name='subjectbox']"
    _BODY          = "div[aria-label='Message Body']"
    # Gmail sometimes changes the aria-label on the send button — try both
    _SEND_LABELS   = [
        "div[aria-label='Send ‪(Ctrl-Enter)‬']",
        "div[data-tooltip='Send']",
        "div[aria-label='Send']",
        "div[jsaction*='send']",
    ]

    def __init__(self, browser):
        """
        Parameters
        ----------
        browser : BrowserTool   shared browser instance from the orchestrator
        """
        self._browser = browser

    async def send(self, to: str, subject: str, body: str) -> str:
        """Open Gmail and send an email. Returns a status message."""
        if not to:
            return "Cannot send: no recipient address provided."

        page = self._browser.page
        if page is None:
            return "Browser is not open. Ask Samantha to open a website first."

        try:
            # ── 1. Navigate to Gmail ───────────────────────────────────
            current = await self._browser.current_url()
            if "mail.google.com" not in current:
                await page.goto(self._GMAIL, wait_until="networkidle")

            # ── 2. Wait for inbox to load ──────────────────────────────
            try:
                await page.wait_for_selector(self._COMPOSE, timeout=20_000)
            except Exception:
                return (
                    "Gmail didn't fully load, or you're not logged in. "
                    "Please log into Gmail in the browser window that opened, "
                    "then try again."
                )

            # ── 3. Click Compose ───────────────────────────────────────
            await page.click(self._COMPOSE)
            await asyncio.sleep(1.0)

            # ── 4. Fill To ─────────────────────────────────────────────
            await page.wait_for_selector(self._TO, timeout=5_000)
            await page.fill(self._TO, to)
            await page.keyboard.press("Tab")
            await asyncio.sleep(0.3)

            # ── 5. Fill Subject ────────────────────────────────────────
            await page.wait_for_selector(self._SUBJECT, timeout=5_000)
            await page.fill(self._SUBJECT, subject)
            await page.keyboard.press("Tab")
            await asyncio.sleep(0.3)

            # ── 6. Fill Body ───────────────────────────────────────────
            await page.wait_for_selector(self._BODY, timeout=5_000)
            await page.click(self._BODY)
            await page.keyboard.type(body)
            await asyncio.sleep(0.3)

            # ── 7. Send — try each known selector ─────────────────────
            sent = False
            for selector in self._SEND_LABELS:
                try:
                    await page.click(selector, timeout=2_500)
                    sent = True
                    break
                except Exception:
                    continue

            if not sent:
                # Last resort: keyboard shortcut Ctrl+Enter
                await page.keyboard.press("Control+Return")

            await asyncio.sleep(1.5)
            return f"✅ Email sent to {to} — subject: '{subject}'"

        except Exception as exc:
            if config.DEBUG:
                import traceback; traceback.print_exc()
            return f"Failed to send email: {exc}"
