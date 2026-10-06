import os
import socket
import requests
import random
from urllib.parse import quote
from dotenv import load_dotenv

# ── Force IPv4 for all outbound HTTP requests ─────────────────────────────────
_orig_getaddrinfo = socket.getaddrinfo


def _ipv4_only(host, port, family=0, type=0, proto=0, flags=0):
    return _orig_getaddrinfo(host, port, socket.AF_INET, type, proto, flags)


socket.getaddrinfo = _ipv4_only
# ─────────────────────────────────────────────────────────────────────────────

_GENERIC_FALLBACKS = [
    "city skyline night cinematic",
    "nature landscape aerial drone",
    "abstract light particles dark",
    "ocean waves aerial sunset",
    "mountain fog morning light",
    "street lights bokeh night",
    "forest sunlight rays morning",
    "rain drops window close up",
]

_ARCHIVE_FALLBACKS = [
    "nasa space mission",
    "prelinger city street",
    "historical documentary archive",
    "vintage science film",
    "world war newsreel",
    "ancient civilization history",
    "ocean nature vintage",
    "industrial factory archive",
]

_ARCHIVE_COLLECTIONS = ("collection:nasa", "collection:prelinger", "collection:opensource_movies")


class MediaFetcher:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("PEXELS_API_KEY")
        if not self.api_key or self.api_key == "your_pexels_api_key_here":
            raise ValueError("PEXELS_API_KEY is missing or not configured in .env")

        self.headers = {"Authorization": self.api_key}
        self.source_mode = os.getenv("VIDEO_SOURCE", "pexels").lower().strip()
        self.archive_max_bytes = int(os.getenv("ARCHIVE_MAX_MB", "120")) * 1_000_000
        self._used_video_ids = set()
        self._used_archive_keys = set()

    def _source_for_slot(self, index: int) -> str:
        if self.source_mode == "archive":
            return "archive"
        if self.source_mode == "hybrid":
            return "archive" if index % 2 else "pexels"
        return "pexels"

    def _search_pexels(self, query, min_duration=5):
        # Repurposed to use DuckDuckGo Search (ddgs) which yields highly accurate movie stills
        try:
            from ddgs import DDGS
            with DDGS() as ddgs:
                results = list(ddgs.images(query, max_results=15))
                
                valid_links = []
                for r in results:
                    link = r.get('image', '')
                    if link and link.lower().endswith(('.jpg', '.jpeg', '.png')):
                        valid_links.append(link)

                if not valid_links:
                    return None, None, False

                # Try to pick a relevant image, avoiding already used links
                selected_link = None
                for link in valid_links:
                    pic_id = link.split('/')[-1]
                    if pic_id not in self._used_video_ids:
                        selected_link = link
                        break
                
                if not selected_link:
                    selected_link = valid_links[0]
                    pic_id = selected_link.split('/')[-1]

                return selected_link, pic_id, True
        except Exception as e:
            print(f"  [!] DDGS Search Error for '{query}': {e}")
            return None, None, False

    def _archive_lucene_query(self, keyword: str) -> str:
        terms = [t for t in keyword.split() if len(t) > 2][:4]
        if not terms:
            terms = ["history"]
        term_q = " OR ".join(f"title:{t} OR subject:{t}" for t in terms)
        collection_q = " OR ".join(_ARCHIVE_COLLECTIONS)
        return f"mediatype:movies AND format:MPEG4 AND ({collection_q}) AND ({term_q})"

    def _pick_archive_file(self, identifier: str):
        meta = requests.get(f"https://archive.org/metadata/{identifier}", timeout=25).json()
        mp4s = [
            f for f in meta.get("files", [])
            if f.get("name", "").lower().endswith(".mp4")
            and int(f.get("size", 0) or 0) <= self.archive_max_bytes
            and int(f.get("size", 0) or 0) >= 500_000
        ]
        if not mp4s:
            return None
        mp4s.sort(key=lambda f: int(f.get("size", 0) or 0), reverse=True)
        chosen = mp4s[0]
        name = chosen["name"]
        url = f"https://archive.org/download/{quote(identifier, safe='')}/{quote(name, safe='')}"
        return url, f"{identifier}/{name}"

    def _search_archive(self, keyword: str):
        query = self._archive_lucene_query(keyword)
        params = {
            "q": query,
            "fl[]": ["identifier", "title"],
            "rows": 25,
            "page": random.randint(1, 2),
            "output": "json",
            "sort[]": "downloads desc",
        }
        try:
            response = requests.get(
                "https://archive.org/advancedsearch.php", params=params, timeout=20
            )
            if response.status_code != 200:
                return None, None, False
            docs = response.json().get("response", {}).get("docs", [])
            random.shuffle(docs)
            for doc in docs:
                ident = doc.get("identifier")
                if not ident:
                    continue
                key = ident
                if key in self._used_archive_keys:
                    continue
                picked = self._pick_archive_file(ident)
                if not picked:
                    continue
                url, archive_key = picked
                if archive_key in self._used_archive_keys:
                    continue
                self._used_archive_keys.add(archive_key)
                return url, archive_key, True
            return None, None, False
        except Exception:
            return None, None, False

    def _find_pexels_video(self, keyword, index, min_duration=5):
        words = keyword.split()
        candidates = [keyword]
        if len(words) >= 4:
            candidates.append(" ".join(words[:3]))
        if len(words) >= 3:
            candidates.append(" ".join(words[:2]))
        if len(words) >= 2:
            candidates.append(words[0])
        candidates.append(_GENERIC_FALLBACKS[index % len(_GENERIC_FALLBACKS)])

        for attempt in candidates:
            url, vid_id, found = self._search_pexels(attempt, min_duration)
            if found:
                if attempt != keyword:
                    print(f"  (broadened Pexels search '{keyword}' → '{attempt}')")
                self._used_video_ids.add(vid_id)
                return url
        return None

    def _find_archive_video(self, keyword, index):
        words = keyword.split()
        candidates = [keyword]
        if len(words) >= 3:
            candidates.append(" ".join(words[:2]))
        if len(words) >= 2:
            candidates.append(words[0])
        candidates.append(_ARCHIVE_FALLBACKS[index % len(_ARCHIVE_FALLBACKS)])

        for attempt in candidates:
            url, archive_key, found = self._search_archive(attempt)
            if found:
                if attempt != keyword:
                    print(f"  (broadened Archive search '{keyword}' → '{attempt}')")
                return url
        return None

    def _find_video(self, keyword, index, min_duration=5):
        source = self._source_for_slot(index)
        if source == "archive":
            return self._find_archive_video(keyword, index), "archive"
        return self._find_pexels_video(keyword, index, min_duration), "pexels"

    def _download_video(self, video_url: str, output_file: str) -> bool:
        print(f"  Downloading video...")
        for attempt in range(3):
            try:
                vid_resp = requests.get(video_url, stream=True, timeout=120)
                vid_resp.raise_for_status()
                with open(output_file, "wb") as f:
                    for chunk in vid_resp.iter_content(chunk_size=65536):
                        if chunk:
                            f.write(chunk)
                if os.path.getsize(output_file) < 10240:
                    print(f"  [!] Downloaded file too small, skipping")
                    os.remove(output_file)
                    return False
                print(f"  [OK] Downloaded to {output_file}")
                return True
            except Exception as e:
                if attempt < 2:
                    print(f"  [retry {attempt + 1}] Download error: {e}")
                else:
                    print(f"  [!] Failed after 3 attempts: {e}")
        return False

    def fetch_background_videos(self, keywords: list, min_duration=5) -> list:
        """
        Download one background clip per keyword.
        VIDEO_SOURCE: pexels (default), archive, or hybrid (alternating slots).
        Returns list of dicts: {"path": str, "source": "pexels"|"archive", "keyword": str}
        """
        downloaded = []
        for i, query in enumerate(keywords):
            output_file = f"temp/temp_bg_{i}.jpg"
            source = self._source_for_slot(i)
            label = "Archive.org" if source == "archive" else "Pexels"
            print(f"[{i + 1}/{len(keywords)}] Searching {label} for: '{query}'...")

            video_url, resolved_source = self._find_video(query, i, min_duration)
            if not video_url:
                print(f"  All fallbacks failed for slot {i + 1}, skipping.")
                continue

            if self._download_video(video_url, output_file):
                downloaded.append({
                    "path": output_file,
                    "source": resolved_source,
                    "keyword": query,
                })
        return downloaded

    def fetch_background_video_paths(self, keywords: list, min_duration=5) -> list:
        """Backward-compatible: return plain file paths only."""
        return [item["path"] for item in self.fetch_background_videos(keywords, min_duration)]


if __name__ == "__main__":
    try:
        fetcher = MediaFetcher()
        files = fetcher.fetch_background_videos(["ocean waves", "nasa moon"], min_duration=5)
        print(f"Downloaded: {files}")
    except Exception as e:
        print(f"Error: {e}")
