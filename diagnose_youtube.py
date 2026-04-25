import os
import json
from src.youtube_uploader import YouTubeUploader
from dotenv import load_dotenv
import googleapiclient.discovery
import googleapiclient.errors

def diagnose_youtube():
    load_dotenv()
    print("=== YouTube Integration Diagnostic ===")
    
    # 1. Check files
    print(f"Checking files...")
    for f in ['client_secrets.json', 'token.json']:
        exists = os.path.exists(f)
        print(f"  {f}: {'EXISTS' if exists else 'MISSING'}")
        if exists:
            try:
                with open(f, 'r') as j:
                    json.load(j)
                print(f"    {f} is valid JSON")
            except Exception as e:
                print(f"    ERROR: {f} is NOT valid JSON: {e}")

    # 2. Test Authentication
    print("\nTesting Authentication...")
    try:
        uploader = YouTubeUploader()
        youtube = uploader.authenticate()
        print("  Service built successfully.")
        
        # We only have 'youtube.upload' scope, so we can't do many 'list' calls.
        # But we can try to get the 'mine' channel (sometimes works with upload scope, sometimes not)
        try:
            request = youtube.channels().list(part="id,snippet", mine=True)
            response = request.execute()
            print(f"  Authenticated as Channel: {response['items'][0]['snippet']['title']} ({response['items'][0]['id']})")
        except Exception as e:
            print(f"  Note: Could not list channel info (likely due to limited 'youtube.upload' scope): {e}")
            print("  This is normal if you only have the upload scope.")

        # 3. Check for specific common errors
        print("\nChecking for common API issues...")
        # Try a tiny metadata-only update or something harmless? 
        # Actually, let's just try to 'list' categories - it's a public call usually.
        try:
            cat_request = youtube.videoCategories().list(part="snippet", regionCode="US")
            cat_response = cat_request.execute()
            print(f"  Successfully fetched {len(cat_response['items'])} video categories. API is RESPONDING.")
        except Exception as e:
            print(f"  ERROR: API call failed: {e}")

    except Exception as e:
        print(f"\nCRITICAL AUTHENTICATION ERROR: {e}")
        if "invalid_grant" in str(e):
            print("  REASON: Refresh token is expired or revoked. You MUST delete 'token.json' and re-authenticate.")
        elif "quotaExceeded" in str(e):
            print("  REASON: Quota exceeded.")

if __name__ == "__main__":
    diagnose_youtube()
