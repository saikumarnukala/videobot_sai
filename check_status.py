import os
from src.youtube_uploader import YouTubeUploader
from dotenv import load_dotenv

def check_video_status(video_id):
    load_dotenv()
    print(f"Checking status of Video ID: {video_id}")
    try:
        uploader = YouTubeUploader()
        youtube = uploader.authenticate()
        
        request = youtube.videos().list(
            part="snippet,status,contentDetails",
            id=video_id
        )
        response = request.execute()
        
        if not response['items']:
            print("Video NOT FOUND. It might have been deleted or the ID is wrong.")
            return

        video = response['items'][0]
        print(f"Title: {video['snippet']['title']}")
        print(f"Privacy Status: {video['status']['privacyStatus']}")
        print(f"Upload Status: {video['status']['uploadStatus']}")
        print(f"Rejection Reason: {video['status'].get('rejectionReason', 'None')}")
        
    except Exception as e:
        print(f"Error checking video status: {e}")

if __name__ == "__main__":
    check_video_status("imCoAfSUmuE")
