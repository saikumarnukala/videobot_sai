import os
import json
import random
import socket
import requests
from pathlib import Path
from typing import Any, Dict, List
from dotenv import load_dotenv

# ── Force IPv4 for all outbound HTTP requests ─────────────────────────────────
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only
# ─────────────────────────────────────────────────────────────────────────────

USED_TOPICS_FILE = "used_topics.json"
CATALOG_PATH = Path(__file__).parent.parent / "assets" / "youtube_bgm_catalog.json"
YOUTUBE_LIBRARY_URL = "https://www.youtube.com/audiolibrary/music"
DRIVE_DOWNLOAD_URL = "https://docs.google.com/uc?export=download&id={track_id}"


def _load_used_music() -> set:
    if os.path.exists(USED_TOPICS_FILE):
        with open(USED_TOPICS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return {str(tid) for tid in data.get("used_music", [])}
    return set()


def _save_used_music(track_id: str):
    data = {}
    if os.path.exists(USED_TOPICS_FILE):
        with open(USED_TOPICS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
    used = data.setdefault("used_music", [])
    if str(track_id) not in [str(t) for t in used]:
        used.append(str(track_id))
        with open(USED_TOPICS_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        print(f"[MusicTracker] Marked track {track_id} as used ({len(used)} total)")


def _topic_keywords(topic: str) -> List[str]:
    """Keywords to score YouTube Audio Library track names against the video topic."""
    topic_lower = topic.lower()
    keywords = set(w for w in topic_lower.replace(",", " ").split() if len(w) > 3)

    if any(w in topic_lower for w in ["motivat", "success", "goal", "growth", "mindset",
                                       "wealth", "money", "business", "achieve"]):
        keywords.update(["hope", "dream", "inspire", "calm", "morning", "uplift"])
    if any(w in topic_lower for w in ["brain", "psychology", "facts", "science", "history",
                                       "secret", "hidden", "truth"]):
        keywords.update(["meditation", "mysterious", "reflection", "thought", "mind"])
    if any(w in topic_lower for w in ["space", "universe", "tech", "ai", "future"]):
        keywords.update(["dream", "sky", "ambient", "ethereal", "space"])
    if any(w in topic_lower for w in ["calm", "meditat", "mindful", "relax", "peaceful",
                                       "ocean", "nature", "forest"]):
        keywords.update(["calm", "peace", "meditation", "nature", "water", "gentle"])
    if any(w in topic_lower for w in ["scary", "horror", "dark", "danger"]):
        keywords.update(["dark", "tension", "mysterious"])

    keywords.update(["calm", "ambient", "acoustic", "meditation", "piano", "peace"])
    return list(keywords)


class MusicFetcher:
    """
    Downloads calm background music from the YouTube Audio Library
    (studio.youtube.com → Audio library). Uses a bundled catalog of
    copyright-safe tracks with Google Drive download IDs.
    """

    def __init__(self):
        load_dotenv()
        catalog_path = os.getenv("YOUTUBE_BGM_CATALOG", str(CATALOG_PATH))
        self.catalog_path = Path(catalog_path)
        if not self.catalog_path.exists():
            raise ValueError(
                f"YouTube BGM catalog not found at {self.catalog_path}. "
                "Expected assets/youtube_bgm_catalog.json in the repo."
            )
        with open(self.catalog_path, "r", encoding="utf-8") as f:
            catalog = json.load(f)
        self.tracks = catalog.get("tracks", [])
        if not self.tracks:
            raise ValueError("YouTube BGM catalog contains no tracks.")

    def _score_track(self, track: dict, keywords: List[str]) -> int:
        name = track.get("name", "").lower()
        return sum(1 for kw in keywords if kw in name)

    def fetch_music(self, topic: str, output_file: str = "bg_music.mp3") -> Dict[str, Any]:
        print("Selecting background music from YouTube Audio Library...")
        keywords = _topic_keywords(topic)
        scored = [(self._score_track(t, keywords), t) for t in self.tracks]
        scored.sort(key=lambda x: x[0], reverse=True)

        used_ids = _load_used_music()
        pool_size = int(os.getenv("YOUTUBE_BGM_POOL_SIZE", "20"))
        top_tracks = [t for _, t in scored[:pool_size]]
        fresh = [t for t in top_tracks if str(t["id"]) not in used_ids]
        if not fresh:
            print("[Music] All top YouTube library picks already used — resetting pool")
            fresh = top_tracks

        track = random.choice(fresh)
        track_id = track["id"]
        track_name = track.get("name", "Unknown Track")
        print(f"Found: '{track_name}' (YouTube Audio Library, ID: {track_id})")
        print("Downloading...")

        download_url = DRIVE_DOWNLOAD_URL.format(track_id=track_id)
        audio_resp = requests.get(download_url, stream=True, timeout=60)
        if audio_resp.status_code != 200:
            raise Exception(f"Failed to download track: HTTP {audio_resp.status_code}")

        os.makedirs(os.path.dirname(output_file) or ".", exist_ok=True)
        with open(output_file, "wb") as f:
            for chunk in audio_resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        _save_used_music(str(track_id))
        print(f"Background music saved to '{output_file}'!")

        return {
            "file_path": output_file,
            "track": {
                "id": track_id,
                "name": track_name,
                "artist_name": "YouTube Audio Library",
                "shareurl": YOUTUBE_LIBRARY_URL,
                "source": "youtube_audio_library",
            },
        }


if __name__ == "__main__":
    fetcher = MusicFetcher()
    fetcher.fetch_music("motivational quotes for success", output_file="temp/bgm_test.mp3")
