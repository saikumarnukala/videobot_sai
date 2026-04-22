import os
import sys
import json
import argparse
import signal
import subprocess
from dotenv import load_dotenv

# Import our custom modules
from src.script_generator import ScriptGenerator
from src.create_audio import AudioGenerator
from src.media_fetcher import MediaFetcher
from src.build_video import VideoBuilder
from src.youtube_uploader import YouTubeUploader
from src.music_fetcher import MusicFetcher
from src.news_fetcher import NewsFetcher
from select_topic import _load_used_topics, _save_used_topics

VERSION = "3.11"

def _mark_topic_used(topic: str):
    """Record a topic in used_topics.json so it is never repeated."""
    data = _load_used_topics()
    used = data.setdefault("used", [])
    if topic not in used:
        used.append(topic)
        _save_used_topics(data)
        print(f"[TopicTracker] Marked as used ({len(used)} total)")


def run_pipeline():
    print(f"=== FACELESS VIDEO BOT v{VERSION} — PIPELINE STARTED ===")

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

    # Mark this topic as used so it never repeats
    _mark_topic_used(topic)

    # Ensure working directories exist (required on fresh CI runners)
    os.makedirs("temp", exist_ok=True)
    os.makedirs("output", exist_ok=True)

    print(f"\n[1/7] Generating Script & 8 Cinematic Scenes for topic: '{topic}'...")
    script_gen = ScriptGenerator()
    script_text, keywords = script_gen.generate_script(topic, length_seconds=target_length)

    print("\n--- SCRIPT ---")
    print(script_text)
    print(f"--- SCENES ({len(keywords)} keywords) ---")
    print(keywords)
    print("--------------\n")

    # 2. Audio Generation
    print(f"\n[2/7] Generating Voiceover...")
    audio_gen = AudioGenerator()
    audio_file = "temp/temp_audio.mp3"
    audio_gen.generate_audio(script_text, output_file=audio_file)

    # 3. Download Background Media (8 unique clips)
    print(f"\n[3/7] Fetching {len(keywords)} Background Videos (full-HD, deduplicated)...")
    media_fetcher = MediaFetcher()
    video_files = media_fetcher.fetch_background_videos(keywords, min_duration=5)
    if not video_files:
        raise RuntimeError("All Pexels video downloads failed. Cannot build video. Check PEXELS_API_KEY and API quota.")

    # 4. Download Background Music from Jamendo
    print(f"\n[4/7] Fetching Background Music from Jamendo...")
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

    # 5. Build Final Video (cinematic Ken Burns + subtitles + high-quality encode)
    print(f"\n[5/7] Rendering Final Video (Ken Burns effects, subtitles, CRF-18)...")
    video_builder = VideoBuilder()
    final_output = "output/final_short.mp4"
    video_builder.build_final_video(
        video_paths=video_files,
        audio_path=audio_file,
        output_path=final_output,
        script_text=script_text,
    )

    # 6. Upload to YouTube
    print(f"\n[6/7] Checking YouTube Upload Status...")
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
            scene_tags  = ["".join(k.split()).lower() for k in keywords[:5]]
            fixed_tags  = ["shorts", "shortsvideo", "viral", "trending", "facts",
                           "youtubeshorts", "reels", "shortsfeed"]
            all_hashtags = list(dict.fromkeys(
                ["#" + t for t in (scene_tags + topic_tags + fixed_tags)]
            ))[:15]

            # --- Description: hook + hashtags + music credit ---
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
                music_credit = f"\n\n🎵 Music: {track_name} — {artist_name} (via Jamendo, CC BY)"
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

    print(f"\n=== PIPELINE SUCCESS v{VERSION}: '{final_output}' ===")

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
    # Setup signal handlers to ensure child processes (ffmpeg) are killed on abort
    def _terminate_and_kill_ffmpeg(signum, frame):
        print("[Main] Received termination signal, attempting to kill ffmpeg...", file=sys.stderr)
        try:
            if os.name == 'nt':
                subprocess.run(["taskkill", "/F", "/T", "/IM", "ffmpeg.exe"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            else:
                subprocess.run(["pkill", "-f", "ffmpeg"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass
        sys.exit(1)

    try:
        signal.signal(signal.SIGINT, _terminate_and_kill_ffmpeg)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, _terminate_and_kill_ffmpeg)
    except Exception:
        # Signal setup might fail on some platforms; ignore and continue
        pass

    try:
        run_pipeline()
    except Exception as e:
        print(f"\n[!] Pipeline Failed: {e}")
        sys.exit(1)
