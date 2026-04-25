import os
from src.youtube_uploader import YouTubeUploader
from dotenv import load_dotenv

def test_upload_realistic():
    load_dotenv()
    print("Testing Realistic YouTube Upload...")
    try:
        uploader = YouTubeUploader()
        test_file = "final_shortTEMP_MPY_wvf_snd.mp4"
        
        # Mimic main.py logic
        topic = "Space Exploration #Shorts"
        video_title = f"{topic} #Shorts"
        description = "Check out this amazing space fact! #shorts #viral #space"
        api_tags = ["shorts", "viral", "space"]

        print(f"  Title      : {video_title}")
        
        video_id = uploader.upload_short(
            file_path=test_file,
            title=video_title,
            description=description,
            privacy_status="private",
            tags=api_tags
        )
        print(f"Successfully uploaded! Video ID: {video_id}")
        
    except Exception as e:
        print(f"Upload Failed: {e}")

if __name__ == "__main__":
    test_upload_realistic()
