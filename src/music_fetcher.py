import os
import random
import requests
from dotenv import load_dotenv

class MusicFetcher:
    """
    Downloads royalty-free background music from Jamendo's free music API.
    Jamendo provides Creative Commons licensed music - completely free & safe for YouTube.
    
    Get your free Client ID at: https://developer.jamendo.com/
    Registration is free and takes 2 minutes.
    """
    
    def __init__(self):
        load_dotenv()
        self.client_id = os.getenv("JAMENDO_CLIENT_ID")
        if not self.client_id or self.client_id == "your_jamendo_client_id_here":
            raise ValueError("JAMENDO_CLIENT_ID is missing in .env! Get a free key at https://developer.jamendo.com/")

    def _map_topic_to_tags(self, topic: str) -> str:
        """
        Intelligently maps the video topic to Jamendo music tags.
        """
        topic_lower = topic.lower()
        
        if any(w in topic_lower for w in ["motivat", "success", "goal", "hustle", "growth"]):
            return "energetic,uplifting"
        elif any(w in topic_lower for w in ["calm", "meditat", "mindful", "relax", "peaceful"]):
            return "ambient,peaceful"
        elif any(w in topic_lower for w in ["scary", "horror", "dark", "creepy", "danger"]):
            return "dark,suspense"
        elif any(w in topic_lower for w in ["happy", "funny", "comedy", "joy"]):
            return "happy,pop"
        elif any(w in topic_lower for w in ["space", "universe", "science", "tech", "ai", "future"]):
            return "electronic,ambient"
        elif any(w in topic_lower for w in ["nature", "travel", "adventure", "explore"]):
            return "acoustic,uplifting"
        else:
            # Default: upbeat and positive
            return "uplifting,instrumental"

    def fetch_music(self, topic: str, output_file: str = "bg_music.mp3") -> str:
        """
        Downloads background music relevant to the video topic.
        Saves it as 'bg_music.mp3' ready for the video builder to pick up.
        """
        tags = self._map_topic_to_tags(topic)
        print(f"Downloading background music (tags: '{tags}')...")

        url = "https://api.jamendo.com/v3.0/tracks/"
        params = {
            "client_id": self.client_id,
            "format": "json",
            "limit": 20,
            "tags": tags,
            "include": "musicinfo",
            "audioformat": "mp31",  # standard mp3
            "order": "popularity_total",
            "durationbetween": "60_300" # 1 to 5 minutes
        }

        response = requests.get(url, params=params, timeout=10)
        if response.status_code != 200:
            raise Exception(f"Jamendo API error {response.status_code}: {response.text}")

        data = response.json()
        tracks = [t for t in data.get("results", []) if t.get("audio")]

        if not tracks:
            raise Exception(f"No music tracks found on Jamendo for tags: {tags}")

        # Pick a random track from top results for variety
        track = random.choice(tracks[:10])
        audio_url = track["audio"]
        
        print(f"Found: '{track['name']}' by {track['artist_name']}")
        print(f"Downloading...")

        audio_resp = requests.get(audio_url, stream=True, timeout=30)
        if audio_resp.status_code != 200:
            raise Exception(f"Failed to download audio: {audio_resp.status_code}")

        with open(output_file, "wb") as f:
            for chunk in audio_resp.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)

        print(f"Background music saved to '{output_file}'!")
        return output_file


if __name__ == "__main__":
    fetcher = MusicFetcher()
    fetcher.fetch_music("motivational quotes for success")
