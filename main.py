import os
import sys
from dotenv import load_dotenv

# Import our custom modules
from src.script_generator import ScriptGenerator
from src.create_audio import AudioGenerator
from src.media_fetcher import MediaFetcher
from src.build_video import VideoBuilder
from src.youtube_uploader import YouTubeUploader
from src.music_fetcher import MusicFetcher

def run_pipeline():
    print("=== FACELESS VIDEO BOT PIPELINE STARTED (V2) ===")
    
    # 1. Setup & Config
    load_dotenv()
    topic = os.getenv("VIDEO_TOPIC", "interesting facts about space")
    target_length = int(os.getenv("VIDEO_LENGTH_SECONDS", "45"))
    upload_enabled = os.getenv("UPLOAD_TO_YOUTUBE", "False").lower() in ("true", "1", "yes")
    
    print(f"\n[1/5] Generating Script & Scenes for topic: '{topic}'...")
    script_gen = ScriptGenerator()
    script_text, keywords = script_gen.generate_script(topic, length_seconds=target_length)
    
    print("\n--- SCRIPT ---")
    print(script_text)
    print("--- SCENES ---")
    print(keywords)
    print("--------------\n")

    # 2. Audio Generation
    print(f"\n[2/5] Generating Voiceover & Subtitles...")
    audio_gen = AudioGenerator()
    audio_file = "temp_audio.mp3"
    subs_file = "temp_subs.json"
    audio_gen.generate_audio_and_subs(script_text, output_file=audio_file, subtitle_file=subs_file)

    # 3. Download Background Media
    print(f"\n[3/5] Fetching Background Videos...")
    media_fetcher = MediaFetcher()
    # It will fetch one video for each keyword the AI came up with!
    video_files = media_fetcher.fetch_background_videos(keywords, min_duration=5)

    # 4. Download Background Music from Jamendo
    print(f"\n[4/6] Fetching Background Music from Jamendo...")
    try:
        music_fetcher = MusicFetcher()
        music_fetcher.fetch_music(topic, output_file="bg_music.mp3")
    except Exception as e:
        print(f"[!] Music fetch failed (will render without music): {e}")

    # 5. Build Final Video
    print(f"\n[4/5] Rendering Final Video with Situational Clips, BGM & Subtitles...")
    video_builder = VideoBuilder()
    final_output = "final_short.mp4"
    video_builder.build_final_video(
        video_paths=video_files, 
        audio_path=audio_file, 
        subtitle_path=subs_file, 
        output_path=final_output
    )

    # 5. Upload to YouTube
    print(f"\n[5/5] Checking YouTube Upload Status...")
    if upload_enabled:
        try:
            print("Upload is ENABLED! Connecting to YouTube...")
            uploader = YouTubeUploader()
            video_title = f"{topic.title()} #Shorts"
            # Extract a short description from the script
            description = f"{script_text[:100]}...\n\n#shorts #viral #{''.join(keywords[0].split())}"
            
            uploader.upload_short(file_path=final_output, title=video_title, description=description)
        except Exception as e:
            print(f"YouTube Upload Failed (Is your client_secrets.json missing?): {e}")
    else:
        print("Upload is DISABLED via .env file. Skipping upload so you can preview it locally!")

    print(f"\n=== PIPELINE SUCCESS: '{final_output}' ===")

if __name__ == "__main__":
    try:
        run_pipeline()
    except Exception as e:
        print(f"\n[!] Pipeline Failed: {e}")
        sys.exit(1)
