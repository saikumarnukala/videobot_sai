import os
import sys
import argparse
from dotenv import load_dotenv

# Import our custom modules
from src.script_generator import ScriptGenerator
from src.create_audio import AudioGenerator
from src.media_fetcher import MediaFetcher
from src.build_video import VideoBuilder
from src.youtube_uploader import YouTubeUploader
from src.music_fetcher import MusicFetcher
from src.news_fetcher import NewsFetcher

def run_pipeline():
    print("=== FACELESS VIDEO BOT PIPELINE STARTED (V3) ===")
    
    parser = argparse.ArgumentParser()
    parser.add_argument('--topic', type=str, help='Override the topic from .env')
    parser.add_argument('--news', action='store_true', help='Fetch a live breaking news topic')
    parser.add_argument('--news-index', type=int, default=0,
                        help='Which news story to use (0=top, 1=second, 2=third)')
    args = parser.parse_args()
    
    # 1. Setup & Config
    load_dotenv()
    if args.topic:
        topic = args.topic
    elif args.news:
        topic = NewsFetcher().get_breaking_topic(index=args.news_index)
    else:
        topic = os.getenv("VIDEO_TOPIC", "interesting facts about space")
    target_length = int(os.getenv("VIDEO_LENGTH_SECONDS", "45"))
    upload_enabled = os.getenv("UPLOAD_TO_YOUTUBE", "False").lower() in ("true", "1", "yes")

    # Ensure working directories exist (required on fresh CI runners)
    os.makedirs("temp", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    print(f"\n[1/6] Generating Script & Scenes for topic: '{topic}'...")
    script_gen = ScriptGenerator()
    script_text, keywords = script_gen.generate_script(topic, length_seconds=target_length)
    
    print("\n--- SCRIPT ---")
    print(script_text)
    print("--- SCENES ---")
    print(keywords)
    print("--------------\n")

    # 2. Audio Generation
    print(f"\n[2/6] Generating Voiceover...")
    audio_gen = AudioGenerator()
    audio_file = "temp/temp_audio.mp3"
    audio_gen.generate_audio(script_text, output_file=audio_file)

    # 3. Download Background Media
    print(f"\n[3/6] Fetching Background Videos...")
    media_fetcher = MediaFetcher()
    # It will fetch one video for each keyword the AI came up with!
    video_files = media_fetcher.fetch_background_videos(keywords, min_duration=5)
    if not video_files:
        raise RuntimeError("All Pexels video downloads failed. Cannot build video. Check PEXELS_API_KEY and API quota.")

    # 4. Download Background Music from Jamendo
    print(f"\n[4/6] Fetching Background Music from Jamendo...")
    # None means music fetch failed and video will render/upload without track attribution.
    selected_music = None
    try:
        music_fetcher = MusicFetcher()
        music_result = music_fetcher.fetch_music(
            topic,
            output_file="temp/bg_music.mp3"
        )
        selected_music = music_result.get("track")
    except Exception as e:
        print(f"[!] Music fetch failed (will render without music): {e}")

    # 5. Build Final Video
    print(f"\n[5/6] Rendering Final Video with Situational Clips & BGM...")
    video_builder = VideoBuilder()
    final_output = "output/final_short.mp4"
    video_builder.build_final_video(
        video_paths=video_files,
        audio_path=audio_file,
        output_path=final_output
    )

    # 6. Upload to YouTube
    print(f"\n[6/6] Checking YouTube Upload Status...")
    if upload_enabled:
        try:
            print("Upload is ENABLED! Connecting to YouTube...")
            uploader = YouTubeUploader()

            # --- Title: clean, punchy, max 70 chars (YouTube limit is 100) ---
            raw_title = topic.title()
            video_title = f"{raw_title} #Shorts"
            if len(video_title) > 70:
                video_title = f"{raw_title[:65]}... #Shorts"

            # --- Hashtags: from keywords + topic words + fixed viral tags ---
            topic_tags  = [w.strip().lower() for w in topic.replace("-", " ").split() if len(w) > 3]
            scene_tags  = ["".join(k.split()).lower() for k in keywords]
            fixed_tags  = ["shorts", "shortsvideo", "viral", "trending", "facts",
                           "youtubeshorts", "reels", "shortsfeed"]
            all_hashtags = list(dict.fromkeys(
                ["#" + t for t in (scene_tags + topic_tags + fixed_tags)]
            ))[:15]   # YouTube allows up to 15 hashtags before penalising

            # --- Description: hook sentence + full script teaser + hashtags ---
            hook       = script_text[:150].rsplit(" ", 1)[0] + "..."
            hashtag_str = " ".join(all_hashtags)
            description = (
                f"{hook}\n\n"
                f"Watch till the end! 🔥\n\n"
                f"───────────────────\n"
                f"{hashtag_str}"
            )
            if selected_music:
                track_name = selected_music.get("name", "Unknown Track")
                artist_name = selected_music.get("artist_name", "Unknown Artist")
                track_url = selected_music.get("shareurl", "")
                music_credit = f"\n\n🎵 Music: {track_name} — {artist_name} (via Jamendo)"
                if track_url:
                    music_credit += f"\n{track_url}"
                description += music_credit

            # --- Tags array for YouTube API (plain words, no #) ---
            api_tags = [t.lstrip("#") for t in all_hashtags] + ["shortsvideo", "viralvideo"]

            print(f"  Title      : {video_title}")
            print(f"  Hashtags   : {hashtag_str}")

            uploader.upload_short(
                file_path=final_output,
                title=video_title,
                description=description,
                tags=api_tags
            )
        except Exception as e:
            print(f"YouTube Upload Failed (Is your client_secrets.json missing?): {e}")
    else:
        print("Upload is DISABLED via .env file. Skipping upload so you can preview it locally!")

    print(f"\n=== PIPELINE SUCCESS: '{final_output}' ===")

    # 7. Cleanup temp folder
    print("\n[7/7] Cleaning up temporary processing files...")
    temp_dir = "temp"
    if os.path.exists(temp_dir):
        for file in os.listdir(temp_dir):
            file_path = os.path.join(temp_dir, file)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except Exception as e:
                print(f"Warning: Could not delete {file_path}: {e}")

if __name__ == "__main__":
    try:
        run_pipeline()
    except Exception as e:
        print(f"\n[!] Pipeline Failed: {e}")
        sys.exit(1)
