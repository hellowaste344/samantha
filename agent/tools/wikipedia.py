"""
tools/wikipedia.py — Wikipedia article lookup.

Uses the `wikipedia` package (MIT licence, free, no API key required).
Synchronous — wrap in asyncio.to_thread() when calling from async code.
"""
from __future__ import annotations
import config


class WikipediaTool:

    def search(self, query: str, sentences: int = 5) -> str:
        """
        Return a short summary of the Wikipedia article that best matches `query`.
        Handles disambiguation and missing pages gracefully.
        """
        try:
            import wikipedia as wiki
            wiki.set_lang("en")

            # ── Direct page attempt ───────────────────────────────────
            try:
                page    = wiki.page(query, auto_suggest=True, redirect=True)
                summary = wiki.summary(query, sentences=sentences, auto_suggest=True)
                return f"📖 {page.title}\n\n{summary}\n\nMore → {page.url}"

            except wiki.exceptions.DisambiguationError as e:
                opts = e.options[:5]
                bullets = "\n".join(f"  • {o}" for o in opts)
                return (
                    f"'{query}' is ambiguous. Did you mean one of:\n{bullets}\n"
                    "Please say a more specific query."
                )

            except wiki.exceptions.PageError:
                # Try a fuzzy search and return the top result
                results = wiki.search(query, results=3)
                if not results:
                    return f"No Wikipedia article found for '{query}'."
                summary = wiki.summary(results[0], sentences=sentences, auto_suggest=False)
                return f"📖 {results[0]}\n\n{summary}"

        except ImportError:
            return "Wikipedia library not installed. Run: pip install wikipedia"
        except Exception as exc:
            if config.DEBUG:
                print(f"[Wikipedia] Error: {exc}")
            return f"Could not retrieve Wikipedia article: {exc}"
