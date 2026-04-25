import os
from src.youtube_uploader import YouTubeUploader
from dotenv import load_dotenv

def test_large_upload():
    load_dotenv()
    print("Testing Large YouTube Upload (86MB)...")
    try:
        uploader = YouTubeUploader()
        test_file = "output/final_short.mp4"
        if not os.path.exists(test_file):
            print(f"File {test_file} not found. Skipping.")
            return

        print(f"File size: {os.path.getsize(test_file) / 1024 / 1024:.2f} MB")
        
        video_id = uploader.upload_short(
            file_path=test_file,
            title="Large File Test #Shorts",
            description="Testing resumable upload with a real video file.",
            privacy_status="private"
        )
        print(f"Successfully uploaded! Video ID: {video_id}")
        
    except Exception as e:
        print(f"Upload Failed: {e}")

if __name__ == "__main__":
    test_large_upload()
