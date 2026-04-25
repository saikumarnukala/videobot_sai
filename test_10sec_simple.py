#!/usr/bin/env python3
"""Simple 10-second video test without dotenv dependency"""

import os
import sys

# Set environment variables directly
os.environ["VIDEO_LENGTH_SECONDS"] = "10"
os.environ["UPLOAD_TO_YOUTUBE"] = "True"

# Add src to path
sys.path.append('src')

# Mock dotenv if not available
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    print("Note: python-dotenv not installed, using direct env vars")
    # Set minimal required env vars
    os.environ["GITHUB_TOKEN"] = os.getenv("GITHUB_TOKEN", "")
    os.environ["GEMINI_API_KEY"] = os.getenv("GEMINI_API_KEY", "")
    os.environ["GROQ_API_KEY"] = os.getenv("GROQ_API_KEY", "")
    os.environ["VIDEO_TOPIC"] = "Test 10-Second Video for YouTube Upload"

# Now import and run minimal pipeline
print("=== 10-Second Video Test ===")
print("Video Length: 10 seconds")
print("Upload to YouTube: Enabled")

try:
    from src.script_generator import ScriptGenerator
    from src.create_audio import AudioGenerator
    from src.media_fetcher import MediaFetcher
    from src.build_video import VideoBuilder
    from src.youtube_uploader import YouTubeUploader
    
    print("\n[1/7] Generating script...")
    script_gen = ScriptGenerator()
    script_text, keywords = script_gen.generate_script(
        topic="Test 10-Second Video for YouTube Upload",
        length_seconds=10
    )
    
    print(f"Script generated: {len(script_text)} characters")
    print(f"Keywords: {keywords}")
    
    print("\n[2/7] Generating audio...")
    audio_gen = AudioGenerator()
    audio_file = audio_gen.generate_audio(script_text, "temp/test_audio.mp3")
    print(f"Audio saved: {audio_file}")
    
    print("\n[3/7] Fetching media...")
    media_fetcher = MediaFetcher()
    # Use the correct method name: fetch_background_videos
    video_paths = media_fetcher.fetch_background_videos(keywords, min_duration=5)  # Only 3 for 10s video
    print(f"Fetched {len(video_paths)} background videos")
    
    print("\n[4/7] Building video...")
    video_builder = VideoBuilder()
    output_path = video_builder.build_final_video(
        video_paths=video_paths,
        audio_path=audio_file,
        script_text=script_text,
        output_path="output/test_10sec.mp4"
    )
    print(f"Video created: {output_path}")
    
    print("\n[5/7] Checking YouTube upload status...")
    uploader = YouTubeUploader()
    youtube = uploader.authenticate()
    
    if youtube:
        print("YouTube authentication successful!")
        
        # Upload as private for testing
        print("\n[6/7] Uploading to YouTube (as private)...")
        result = uploader.upload_short(
            file_path=output_path,
            title="TEST: 10-Second Video Upload Check",
            description="This is a test upload to verify YouTube integration works correctly. #test #faceless #automation",
            category_id="22",
            privacy_status="private",  # Upload as private
            tags=["test", "automation", "faceless", "shorts"]
        )
        
        if result:
            print(f"\n[7/7] SUCCESS! Video uploaded.")
            print(f"Video ID: {result}")
            print(f"\nCheck your YouTube Studio: https://studio.youtube.com/")
        else:
            print("\n[7/7] Upload failed")
    else:
        print("\n[6/7] YouTube authentication failed")
        
except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
    
print("\n=== Test Complete ===")