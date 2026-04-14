"""
Fetches trending/breaking news headlines from free RSS feeds.
No API key required. Updates in real time.
"""
import random
import re
import feedparser


class NewsFetcher:
    """Fetch the current top breaking news headlines for use as video topics."""

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

    def get_top_stories(self, count: int = 3) -> list:
        """
        Return up to `count` unique video-ready topic strings from today's top news.
        Stories are deduplicated and returned in feed order (most prominent first).
        Falls back gracefully if feeds fail.
        """
        seen = set()
        candidates = []

        for feed_url in self.FEEDS:
            if len(candidates) >= count * 3:  # collect a healthy pool
                break
            try:
                feed = feedparser.parse(feed_url)
                for e in feed.get("entries", [])[:20]:
                    title = getattr(e, "title", "").strip()
                    if len(title) > 25 and not self._SKIP_PATTERNS.search(title):
                        clean = re.split(r"\s[-|]\s", title)[0].strip()
                        # Deduplicate by first 6 words (handles minor phrasing diffs)
                        key = " ".join(clean.lower().split()[:6])
                        if len(clean) > 20 and key not in seen:
                            seen.add(key)
                            candidates.append(clean)
            except Exception as exc:
                print(f"[News] Feed {feed_url} failed: {exc}. Trying next…")
                continue

        if not candidates:
            # Fallback — Gemini/Groq will expand this into a generic current-events script
            return [f"breaking news: biggest story happening right now in the world #{i+1}"
                    for i in range(count)]

        # Return up to `count` stories, cycling if we don't have enough
        result = []
        for i in range(count):
            story = candidates[i % len(candidates)]
            topic = f"breaking news: {story}"
            result.append(topic)
            print(f"[News] Story #{i+1}: {story}")
        return result

    def get_breaking_topic(self, index: int = 0) -> str:
        """
        Return a single topic string. index 0/1/2 picks different stories
        so parallel cron runs don't duplicate content.
        """
        stories = self.get_top_stories(count=max(index + 1, 3))
        return stories[index % len(stories)]
