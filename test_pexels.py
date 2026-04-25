import os
import requests
from dotenv import load_dotenv

def test_pexels():
    load_dotenv()
    api_key = os.getenv("PEXELS_API_KEY")
    print(f"Testing Pexels API with key: {api_key[:5]}...")
    
    url = "https://api.pexels.com/videos/search"
    headers = {"Authorization": api_key}
    params = {"query": "nature", "per_page": 1}
    
    try:
        response = requests.get(url, headers=headers, params=params)
        print(f"Status Code: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            if data.get("videos"):
                print("Successfully fetched video data from Pexels!")
            else:
                print("No videos found (but API works).")
        elif response.status_code == 429:
            print("ERROR: Pexels API Quota Exceeded (Rate Limited).")
        elif response.status_code == 401:
            print("ERROR: Pexels API Key is INVALID.")
        else:
            print(f"ERROR: Pexels API returned: {response.text}")
    except Exception as e:
        print(f"Network error: {e}")

if __name__ == "__main__":
    test_pexels()
