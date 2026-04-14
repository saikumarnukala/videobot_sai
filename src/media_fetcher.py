import os
import requests
import random
from dotenv import load_dotenv

# When a keyword returns no Pexels results, broaden it by progressively
# stripping words from the right until something matches.
_GENERIC_FALLBACKS = [
    "city skyline",
    "nature landscape",
    "abstract background",
]

class MediaFetcher:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("PEXELS_API_KEY")
        if not self.api_key or self.api_key == "your_pexels_api_key_here":
            raise ValueError("PEXELS_API_KEY is missing or not configured in .env")
        
        self.headers = {
            "Authorization": self.api_key
        }

    def _search_pexels(self, query, min_duration=5):
        """Try Pexels search. Returns (video_url, True) on success, (None, False) on miss."""
        url = "https://api.pexels.com/videos/search"
        params = {
            "query": query,
            "orientation": "portrait",
            "size": "medium",
            "per_page": 15,
            "page": random.randint(1, 3),
        }
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=15)
            if response.status_code != 200:
                return None, False
            data = response.json()
            videos = data.get("videos", [])
            if not videos:
                return None, False
            valid = [v for v in videos if v.get("duration", 0) >= min_duration] or videos
            selected = random.choice(valid)
            files = selected.get("video_files", [])
            files.sort(key=lambda x: (x.get("width", 0) * x.get("height", 0)), reverse=True)
            return files[0]["link"], True
        except Exception:
            return None, False

    def _find_video(self, keyword, index, min_duration=5):
        """
        Try progressively broader searches until a video is found:
          1. Full keyword  (e.g. "military ships at sea")
          2. First 2 words (e.g. "military ships")
          3. First word    (e.g. "military")
          4. Generic fallback keyed to index
        """
        words = keyword.split()
        candidates = [keyword]
        if len(words) >= 3:
            candidates.append(" ".join(words[:2]))
        if len(words) >= 2:
            candidates.append(words[0])
        candidates.append(_GENERIC_FALLBACKS[index % len(_GENERIC_FALLBACKS)])

        for attempt in candidates:
            url, found = self._search_pexels(attempt, min_duration)
            if found:
                if attempt != keyword:
                    print(f"  (broadened search '{keyword}' → '{attempt}')")
                return url
        return None

    def fetch_background_videos(self, keywords: list, min_duration=5) -> list:
        """
        Searches Pexels for a vertical video matching each keyword and downloads them.
        Falls back to broader terms so every slot always gets a relevant clip.
        """
        downloaded_files = []
        for i, query in enumerate(keywords):
            output_file = f"temp_bg_{i}.mp4"
            print(f"[{i+1}/{len(keywords)}] Searching Pexels for: '{query}'...")

            video_url = self._find_video(query, i, min_duration)
            if not video_url:
                print(f"  All fallbacks failed for slot {i+1}, skipping.")
                continue

            print(f"  Downloading video for slot {i+1}...")
            vid_resp = requests.get(video_url, stream=True, timeout=60)
            with open(output_file, 'wb') as f:
                for chunk in vid_resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print(f"  ✓ Downloaded to {output_file}")
            downloaded_files.append(output_file)
            
        return downloaded_files

if __name__ == "__main__":
    try:
        fetcher = MediaFetcher()
        files = fetcher.fetch_background_videos(["ocean waves", "dark clouds"], min_duration=10)
        print(f"Downloaded: {files}")
    except Exception as e:
        print(f"Error: {e}")
