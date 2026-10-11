import os
import shutil
from dotenv import load_dotenv

try:
    from src.tmdb_fetcher import TMDBFetcher
except (ImportError, ModuleNotFoundError):
    from tmdb_fetcher import TMDBFetcher


class MediaFetcher:
    """
    Exclusive image extractor for The Movie Database (TMDB - https://www.themoviedb.org).
    Replaces generic web search and extracts official high-definition movie backdrops and posters.
    """

    def __init__(self):
        load_dotenv()
        self.tmdb = TMDBFetcher()

    def fetch_background_video_paths(self, keywords: list, topic: str = None, min_duration: int = 5) -> list[str]:
        """
        Download official high-definition movie images from TMDB (https://www.themoviedb.org).
        Uses topic (or keyword context) to locate the movie on TMDB.
        """
        search_query = topic
        if not search_query and keywords:
            # Fallback to movie name extracted from first keyword
            search_query = keywords[0]
        if not search_query:
            search_query = os.getenv("VIDEO_TOPIC", "Inception")

        count = len(keywords) if keywords else 8
        print(f"\n[MediaFetcher] Fetching {count} official HD stills from TMDB (themoviedb.org) for: '{search_query}'...")
        images = self.tmdb.download_movie_images(search_query, count=count)
        return images

    def fetch_background_videos(self, keywords: list, topic: str = None, min_duration: int = 5) -> list[dict]:
        """Backward-compatible helper returning structured dicts."""
        paths = self.fetch_background_video_paths(keywords, topic=topic, min_duration=min_duration)
        return [
            {
                "path": p,
                "source": "tmdb",
                "keyword": keywords[i] if i < len(keywords) else "tmdb_still",
            }
            for i, p in enumerate(paths)
        ]


if __name__ == "__main__":
    fetcher = MediaFetcher()
    test_keywords = ["Inception poster", "Inception dream city", "Inception spinning top"]
    results = fetcher.fetch_background_video_paths(test_keywords, topic="Review of the movie Inception (2010)")
    print(f"\nFetched {len(results)} TMDB images:")
    for r in results:
        print(f"  {r}")
