"""
Fetches a trending/breaking news headline from free RSS feeds.
No API key required. Updates in real time.
"""
import random
import re
import feedparser


class NewsFetcher:
    """Fetch the current top breaking news headline for use as a video topic."""

    FEEDS = [
        "https://news.google.com/rss?hl=en-US&gl=US&ceid=US:en",
        "https://feeds.bbci.co.uk/news/world/rss.xml",
        "https://rss.reuters.com/reuters/topNews",
        "https://feeds.npr.org/1001/rss.xml",
    ]

    # Patterns to skip — meta/editorial titles, not real stories
    _SKIP_PATTERNS = re.compile(
        r"(RSS|subscribe|newsletter|\[removed\]|opinion:|editorial:|"
        r"reuters\s*-\s*$|bbc\s*-\s*$)",
        re.IGNORECASE,
    )

    def get_breaking_topic(self) -> str:
        """
        Return a video-ready topic string based on today's top news.
        Falls back gracefully if all feeds fail.
        """
        for feed_url in self.FEEDS:
            try:
                feed = feedparser.parse(feed_url)
                entries = feed.get("entries", [])

                candidates = []
                for e in entries[:20]:
                    title = getattr(e, "title", "").strip()
                    # Must be a real story: long enough and not a skip pattern
                    if len(title) > 25 and not self._SKIP_PATTERNS.search(title):
                        # Remove source attribution: "Story title - BBC News"
                        clean = re.split(r"\s[-|]\s", title)[0].strip()
                        if len(clean) > 20:
                            candidates.append(clean)

                if candidates:
                    headline = random.choice(candidates[:5])
                    print(f"[News] Breaking story: {headline}")
                    return f"breaking news: {headline}"

            except Exception as exc:
                print(f"[News] Feed {feed_url} failed: {exc}. Trying next…")
                continue

        # Fallback — Gemini will expand this into a generic current-events script
        return "biggest breaking news story happening right now in the world"
