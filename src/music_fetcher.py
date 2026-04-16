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
        allowed_ids_raw = os.getenv("JAMENDO_ALLOWED_TRACK_IDS", "")
        self.allowed_track_ids = {track_id.strip() for track_id in allowed_ids_raw.split(",") if track_id.strip()}
        self.last_track = None

    def _map_topic_to_tags(self, topic: str) -> str:
        """
        Intelligently maps the video topic to Jamendo music tags.
        Prioritises cinematic, high-production-value mood music.
        """
        topic_lower = topic.lower()
        
        # Motivational / self-improvement / morning topics
        if any(w in topic_lower for w in ["motivat", "success", "goal", "hustle", "growth",
                                           "habit", "discipline", "stoic", "wisdom", "mindset",
                                           "billionaire", "routine", "intelligent", "best",
                                           "dominate", "win", "achieve", "powerful"]):
            return "cinematic+energetic"
        # Money / business / finance topics
        elif any(w in topic_lower for w in ["money", "income", "invest", "wealth", "rich",
                                             "millionaire", "financial", "salary", "business",
                                             "brand", "passive", "hustle", "side", "earn",
                                             "profit", "budget", "negotiate"]):
            return "cinematic+corporate"
        # Science / tech / facts / brain topics
        elif any(w in topic_lower for w in ["brain", "psychology", "facts", "history", "ancient",
                                             "civiliz", "quantum", "physics", "discover", "experiment",
                                             "secret", "hidden", "truth", "mind"]):
            return "cinematic+mysterious"
        # Space / AI / future / tech topics
        elif any(w in topic_lower for w in ["space", "universe", "science", "tech", "ai",
                                             "future", "robot", "technology", "digital"]):
            return "cinematic+electronic"
        # Scary / danger / dark topics
        elif any(w in topic_lower for w in ["scary", "horror", "dark", "creepy", "danger",
                                             "scariest", "terrifying", "nightmare"]):
            return "cinematic+dark"
        # Ocean / nature / travel topics
        elif any(w in topic_lower for w in ["ocean", "sea", "nature", "travel", "adventure",
                                             "explore", "deep", "forest", "mountain"]):
            return "cinematic+ambient"
        # Calm / wellness topics
        elif any(w in topic_lower for w in ["calm", "meditat", "mindful", "relax", "peaceful"]):
            return "cinematic+peaceful"
        # Happy / comedy topics
        elif any(w in topic_lower for w in ["happy", "funny", "comedy", "joy"]):
            return "cinematic+happy"
        # News / politics / war / world events
        elif any(w in topic_lower for w in ["news", "war", "politic", "election", "crisis",
                                             "breaking", "world", "conflict", "govern"]):
            return "cinematic+dramatic"
        else:
            # Default: cinematic and uplifting
            return "cinematic+uplifting"

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

        if self.allowed_track_ids:
            tracks = [t for t in tracks if str(t.get("id")) in self.allowed_track_ids]
            if not tracks:
                raise Exception(
                    f"No Jamendo tracks matched JAMENDO_ALLOWED_TRACK_IDS for tags: {tags}. "
                    "Please update JAMENDO_ALLOWED_TRACK_IDS with valid Jamendo track IDs."
                )

        if not tracks:
            raise Exception(f"No music tracks found on Jamendo for tags: {tags}")

        # Pick a random track from top results for variety
        track = random.choice(tracks[:10])
        audio_url = track["audio"]
        self.last_track = track
        
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
