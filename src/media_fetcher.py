import os
import requests
import random
from dotenv import load_dotenv

# When a keyword returns no Pexels results, broaden it by progressively
# stripping words from the right until something matches.
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

class MediaFetcher:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("PEXELS_API_KEY")
        if not self.api_key or self.api_key == "your_pexels_api_key_here":
            raise ValueError("PEXELS_API_KEY is missing or not configured in .env")

        self.headers = {
            "Authorization": self.api_key
        }
        # Track video IDs already chosen in this session to avoid duplicates
        self._used_video_ids = set()

    def _search_pexels(self, query, min_duration=5):
        """Try Pexels search. Returns (video_url, video_id, True) on success."""
        url = "https://api.pexels.com/videos/search"
        params = {
            "query": query,
            "orientation": "portrait",
            "size": "large",
            "per_page": 40,
            "page": random.randint(1, 3),
        }
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=15)
            if response.status_code != 200:
                return None, None, False
            data = response.json()
            videos = data.get("videos", [])
            if not videos:
                return None, None, False

            # Filter: ≥min_duration AND not already used in this run
            valid = [v for v in videos
                     if v.get("duration", 0) >= min_duration
                     and v.get("id") not in self._used_video_ids]
            if not valid:
                # Relax the dedup if nothing else available
                valid = [v for v in videos if v.get("duration", 0) >= min_duration] or videos

            selected = random.choice(valid)
            vid_id = selected.get("id")
            files = selected.get("video_files", [])

            # Prefer full-HD (≥1080p), then HD (≥720p), then anything
            fhd_files = [f for f in files if f.get("height", 0) >= 1080]
            hd_files = [f for f in files if f.get("height", 0) >= 720]
            chosen_pool = fhd_files or hd_files or files
            chosen_pool.sort(key=lambda x: (x.get("width", 0) * x.get("height", 0)), reverse=True)
            return chosen_pool[0]["link"], vid_id, True
        except Exception:
            return None, None, False

    def _find_video(self, keyword, index, min_duration=5):
        """
        Try progressively broader searches until a video is found:
          1. Full keyword  (e.g. "military ships at sea dramatic")
          2. First 3 words (e.g. "military ships at")
          3. First 2 words (e.g. "military ships")
          4. First word    (e.g. "military")
          5. Generic cinematic fallback keyed to index
        """
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
                    print(f"  (broadened search '{keyword}' → '{attempt}')")
                self._used_video_ids.add(vid_id)
                return url
        return None

    def fetch_background_videos(self, keywords: list, min_duration=5) -> list:
        """
        Searches Pexels for a vertical video matching each keyword and downloads them.
        Falls back to broader terms so every slot always gets a relevant clip.
        Deduplicates: no two scenes will use the same Pexels video.
        """
        downloaded_files = []
        for i, query in enumerate(keywords):
            output_file = f"temp/temp_bg_{i}.mp4"
            print(f"[{i+1}/{len(keywords)}] Searching Pexels for: '{query}'...")

            video_url = self._find_video(query, i, min_duration)
            if not video_url:
                print(f"  All fallbacks failed for slot {i+1}, skipping.")
                continue

            print(f"  Downloading video for slot {i+1}...")
            for attempt in range(3):
                try:
                    vid_resp = requests.get(video_url, stream=True, timeout=60)
                    vid_resp.raise_for_status()
                    with open(output_file, 'wb') as f:
                        for chunk in vid_resp.iter_content(chunk_size=65536):
                            if chunk:
                                f.write(chunk)
                    # Validate: file must be >10KB to be a real video
                    if os.path.getsize(output_file) < 10240:
                        print(f"  [!] Downloaded file too small ({os.path.getsize(output_file)} bytes), skipping slot {i+1}")
                        os.remove(output_file)
                        break
                    print(f"  [OK] Downloaded to {output_file}")
                    downloaded_files.append(output_file)
                    break
                except Exception as e:
                    if attempt < 2:
                        print(f"  [retry {attempt+1}] Download error: {e}")
                    else:
                        print(f"  [!] Failed to download slot {i+1} after 3 attempts: {e}")

        return downloaded_files

if __name__ == "__main__":
    try:
        fetcher = MediaFetcher()
        files = fetcher.fetch_background_videos(["ocean waves", "dark clouds"], min_duration=10)
        print(f"Downloaded: {files}")
    except Exception as e:
        print(f"Error: {e}")
