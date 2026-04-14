import os
import requests
import random
from dotenv import load_dotenv

class MediaFetcher:
    def __init__(self):
        load_dotenv()
        self.api_key = os.getenv("PEXELS_API_KEY")
        if not self.api_key or self.api_key == "your_pexels_api_key_here":
            raise ValueError("PEXELS_API_KEY is missing or not configured in .env")
        
        self.headers = {
            "Authorization": self.api_key
        }

    def fetch_background_videos(self, keywords: list, min_duration=5) -> list:
        """
        Searches Pexels for a vertical video matching each keyword and downloads them.
        """
        downloaded_files = []
        for i, query in enumerate(keywords):
            output_file = f"temp_bg_{i}.mp4"
            print(f"[{i+1}/{len(keywords)}] Searching Pexels for vertical videos of: '{query}'...")
            url = "https://api.pexels.com/videos/search"
            params = {
                "query": query,
                "orientation": "portrait",
                "size": "medium", 
                "per_page": 15
            }
            
            response = requests.get(url, headers=self.headers, params=params)
            
            if response.status_code != 200:
                print(f"Pexels API Error for '{query}': {response.text}")
                continue
                
            data = response.json()
            if not data.get("videos"):
                print(f"No videos found for query: {query}. Using fallback.")
                continue
                
            valid_videos = [v for v in data["videos"] if v.get("duration", 0) >= min_duration]
            
            if not valid_videos:
                valid_videos = data["videos"]
                
            selected_video = random.choice(valid_videos)
            
            # Sort files to find the highest resolution vertical video available
            video_files = selected_video.get("video_files", [])
            video_files.sort(key=lambda x: (x.get("width", 0) * x.get("height", 0)), reverse=True)
            
            best_file = video_files[0]["link"]
            print(f"Downloading HD background video for '{query}'...")
            
            # Stream the download
            vid_resp = requests.get(best_file, stream=True, timeout=60)
            with open(output_file, 'wb') as f:
                for chunk in vid_resp.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                    
            print(f"Video {i+1} downloaded successfully to {output_file}")
            downloaded_files.append(output_file)
            
        return downloaded_files

if __name__ == "__main__":
    try:
        fetcher = MediaFetcher()
        files = fetcher.fetch_background_videos(["ocean waves", "dark clouds"], min_duration=10)
        print(f"Downloaded: {files}")
    except Exception as e:
        print(f"Error: {e}")
